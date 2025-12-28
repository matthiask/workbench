import logging
import re
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


def extract_project_info(project_url: str) -> tuple[str | None, str | None, str | None]:
    """
    Extract owner, repo, and project number from GitHub project URL.

    Args:
        project_url: URL to GitHub project, can be in various formats

    Returns:
        Tuple of (owner, repo, project_number) or (None, None, None) if parsing fails
    """
    # Handle projects URLs in various formats
    patterns = [
        # New project URL: https://github.com/orgs/owner/projects/1
        r"https://github\.com/orgs/([^/]+)/projects/(\d+)",
        # New repo project URL: https://github.com/users/owner/projects/1
        r"https://github\.com/users/([^/]+)/projects/(\d+)",
        # Classic project URL: https://github.com/owner/repo/projects/1
        r"https://github\.com/([^/]+)/([^/]+)/projects/(\d+)",
    ]

    for pattern in patterns:
        match = re.match(pattern, project_url)
        if match:
            groups = match.groups()
            if len(groups) == 3:  # Classic project format
                return groups[0], groups[1], groups[2]
            if len(groups) == 2:  # New project format (org or user)
                return groups[0], None, groups[1]

    logger.error(f"Could not parse GitHub project URL: {project_url}")
    return None, None, None


def get_project_cards(
    project_url: str, api_token: str | None = None
) -> list[dict[str, Any]]:
    """
    Get all cards from a GitHub project with their associated issues and field values.

    Args:
        project_url: URL to GitHub project
        api_token: GitHub API token, defaults to settings.GITHUB_API_TOKEN

    Returns:
        List of dictionaries containing card data with their issues and field values
    """
    token = api_token or getattr(settings, "GITHUB_API_TOKEN", "")
    if not token:
        logger.error("No GitHub API token provided")
        return []

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    owner, repo, project_number = extract_project_info(project_url)
    if not owner or not project_number:
        return []

    # Determine if this is a classic project or a new project (v2)
    project_v2 = repo is None

    if project_v2:
        # Use GraphQL API for Projects v2
        return _get_project_v2_cards(owner, project_number, headers)
    # Use REST API for classic projects
    return _get_classic_project_cards(owner, repo, project_number, headers)


def _get_classic_project_cards(
    owner: str, repo: str, project_number: str, headers: dict[str, str]
) -> list[dict[str, Any]]:
    """Get cards from a classic GitHub project."""
    # Directly access the project - classic projects are being deprecated by GitHub
    # So we'll use the inertia preview header which is required for projects API
    preview_headers = {
        **headers,
        "Accept": "application/vnd.github.inertia-preview+json",
    }

    # Try a few different API routes to find the project
    project_id = None

    # First try to get the project directly by number
    try:
        # For organization projects
        if repo is None:
            org_url = f"https://api.github.com/orgs/{owner}/projects"
            response = requests.get(org_url, headers=preview_headers)

            if response.status_code == 200:
                projects = response.json()
                for project in projects:
                    if str(project.get("number")) == project_number:
                        project_id = project.get("id")
                        break
        else:
            # For repository projects
            repo_url = f"https://api.github.com/repos/{owner}/{repo}/projects"
            response = requests.get(repo_url, headers=preview_headers)

            if response.status_code == 200:
                projects = response.json()
                for project in projects:
                    if str(project.get("number")) == project_number:
                        project_id = project.get("id")
                        break
    except Exception as e:
        logger.exception(f"Error finding project {project_number}: {e!s}")

    # If all else fails, try using the project number as the ID directly
    # This is less reliable but might work in some cases
    if project_id is None:
        logger.warning(
            f"Could not find project ID for {owner}/{repo}/projects/{project_number}"
        )
        logger.warning("Trying to use project number as ID directly")
        project_id = project_number

    # Get columns in the project
    columns_url = f"https://api.github.com/projects/{project_id}/columns"

    response = requests.get(columns_url, headers=preview_headers)
    if response.status_code != 200:
        logger.error(
            f"Failed to fetch columns for project {project_id}: Status {response.status_code}"
        )
        return []

    columns = response.json()
    cards = []

    # For each column, get its cards
    for column in columns:
        column_name = column.get("name", "")
        column_id = column.get("id")

        cards_url = f"https://api.github.com/projects/columns/{column_id}/cards"
        cards_response = requests.get(cards_url, headers=preview_headers)

        if cards_response.status_code != 200:
            logger.warning(
                f"Failed to fetch cards for column {column_id}: Status {cards_response.status_code}"
            )
            continue

        column_cards = cards_response.json()

        for card in column_cards:
            card_data = {
                "id": card.get("id"),
                "column_name": column_name,
                "note": card.get("note"),
                "content_url": card.get("content_url"),
                "issue": None,
                "estimate": None,
            }

            # If card is linked to an issue, fetch issue details
            if card.get("content_url") and "issues" in card.get("content_url", ""):
                issue_response = requests.get(card["content_url"], headers=headers)

                if issue_response.status_code == 200:
                    issue = issue_response.json()
                    card_data["issue"] = {
                        "number": issue.get("number"),
                        "title": issue.get("title"),
                        "html_url": issue.get("html_url"),
                        "body": issue.get("body"),
                        "state": issue.get("state"),
                    }

                    # Try to find estimate in custom fields
                    # For classic projects, the custom field could be in a note or in the issue
                    estimate_patterns = [
                        r"(?:hours|estimate):\s*(\d+(?:\.\d+)?)",
                        r"(\d+(?:\.\d+)?)\s*hours?",
                    ]

                    # Check card note first
                    if card.get("note"):
                        for pattern in estimate_patterns:
                            match = re.search(pattern, card["note"], re.IGNORECASE)
                            if match:
                                card_data["estimate"] = Decimal(match.group(1))
                                break

                    # Then check issue title and body
                    if card_data["estimate"] is None:
                        for content in [issue.get("title", ""), issue.get("body", "")]:
                            if not content:
                                continue

                            for pattern in estimate_patterns:
                                match = re.search(pattern, content, re.IGNORECASE)
                                if match:
                                    card_data["estimate"] = Decimal(match.group(1))
                                    break

                            if card_data["estimate"] is not None:
                                break

            cards.append(card_data)

    return cards


def _get_project_v2_cards(
    owner: str, project_number: str, headers: dict[str, str]
) -> list[dict[str, Any]]:
    """Get cards from a GitHub Projects v2."""
    # Use GraphQL API for Projects v2
    graphql_url = "https://api.github.com/graphql"

    # First, try to get the project by number as an organization project
    project_query = {
        "query": """
        query($owner: String!, $number: Int!) {
          organization(login: $owner) {
            projectV2(number: $number) {
              id
              title
              fields(first: 20) {
                nodes {
                  ... on ProjectV2FieldCommon {
                    id
                    name
                  }
                }
              }
            }
          }
        }
        """,
        "variables": {"owner": owner, "number": int(project_number)},
    }

    response = requests.post(graphql_url, json=project_query, headers=headers)

    # Check if we got a valid response for an organization project
    org_project = False
    if response.status_code == 200:
        result = response.json()
        if (
            "data" in result
            and "organization" in result["data"]
            and result["data"]["organization"] is not None
        ):
            org_data = result["data"]["organization"]
            if "projectV2" in org_data and org_data["projectV2"] is not None:
                org_project = True

    # If not an organization project, try as a user project
    if not org_project:
        user_query = {
            "query": """
            query($owner: String!, $number: Int!) {
              user(login: $owner) {
                projectV2(number: $number) {
                  id
                  title
                  fields(first: 20) {
                    nodes {
                      ... on ProjectV2FieldCommon {
                        id
                        name
                      }
                    }
                  }
                }
              }
            }
            """,
            "variables": {"owner": owner, "number": int(project_number)},
        }

        response = requests.post(graphql_url, json=user_query, headers=headers)

    if response.status_code != 200:
        logger.error(
            f"Failed to fetch project for {owner}/{project_number}: Status {response.status_code}"
        )
        return []

    result = response.json()

    # Extract the correct project path based on whether it's an org or user project
    if org_project:
        project_path = "data.organization.projectV2"
    else:
        project_path = "data.user.projectV2"

    # Navigate to the project data
    project_data = result
    for key in project_path.split("."):
        if key in project_data:
            project_data = project_data[key]
        else:
            logger.error(f"Could not find {key} in GraphQL response")
            return []

    if not project_data:
        logger.error(f"Could not find project {project_number} for {owner}")
        return []

    project_id = project_data.get("id")
    fields = project_data.get("fields", {}).get("nodes", [])

    # Find the field IDs that might contain time estimates
    estimate_field_ids = []
    for field in fields:
        if any(
            term in field.get("name", "").lower()
            for term in ["hour", "time", "estimate", "duration"]
        ):
            estimate_field_ids.append(field.get("id"))

    # Get items in the project with their field values
    items_query = {
        "query": """
        query($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
                nodes {
                  id
                  content {
                    ... on Issue {
                      id
                      number
                      title
                      body
                      url
                      state
                      repository {
                        name
                        owner {
                          login
                        }
                      }
                    }
                    ... on PullRequest {
                      id
                      number
                      title
                      body
                      url
                      state
                      repository {
                        name
                        owner {
                          login
                        }
                      }
                    }
                    ... on DraftIssue {
                      id
                      title
                      body
                    }
                  }
                  fieldValues(first: 20) {
                    nodes {
                      ... on ProjectV2ItemFieldTextValue {
                        text
                        field {
                          ... on ProjectV2FieldCommon {
                            id
                            name
                          }
                        }
                      }
                      ... on ProjectV2ItemFieldNumberValue {
                        number
                        field {
                          ... on ProjectV2FieldCommon {
                            id
                            name
                          }
                        }
                      }
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        field {
                          ... on ProjectV2FieldCommon {
                            id
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """,
        "variables": {"projectId": project_id},
    }

    items_response = requests.post(graphql_url, json=items_query, headers=headers)

    if items_response.status_code != 200:
        logger.error(
            f"Failed to fetch items for project {project_id}: Status {items_response.status_code}"
        )
        return []

    items_data = items_response.json()
    if "data" not in items_data or "node" not in items_data["data"]:
        logger.error("Invalid GraphQL response for items")
        return []

    items = items_data["data"]["node"]["items"]["nodes"]
    cards = []

    for item in items:
        card_data = {
            "id": item.get("id"),
            "issue": None,
            "estimate": None,
        }

        content = item.get("content", {})
        if content:
            # Handle Issue or PR content
            if content.get("repository"):
                card_data["issue"] = {
                    "number": content.get("number"),
                    "title": content.get("title"),
                    "html_url": content.get("url"),
                    "body": content.get("body"),
                    "state": content.get("state"),
                    "repo": content.get("repository", {}).get("name"),
                    "owner": content
                    .get("repository", {})
                    .get("owner", {})
                    .get("login"),
                }
            # Handle Draft Issue content
            elif "title" in content:
                card_data["draft"] = {
                    "title": content.get("title"),
                    "body": content.get("body"),
                }

        # Extract field values
        field_values = item.get("fieldValues", {}).get("nodes", [])
        for field_value in field_values:
            field = field_value.get("field", {})
            field_id = field.get("id")
            field_name = field.get("name", "").lower()

            # Look for estimate in number fields with appropriate names
            if "number" in field_value and (
                field_id in estimate_field_ids
                or any(
                    term in field_name
                    for term in ["hour", "time", "estimate", "duration"]
                )
            ):
                card_data["estimate"] = field_value["number"]
                card_data["estimate_field"] = field_name
                break

        # If no estimate found in custom fields, try the title/body
        if card_data["estimate"] is None and card_data["issue"]:
            estimate_patterns = [
                r"(?:hours|estimate):\s*(\d+(?:\.\d+)?)",
                r"(\d+(?:\.\d+)?)\s*hours?",
            ]

            for content in [
                card_data["issue"].get("title", ""),
                card_data["issue"].get("body", ""),
            ]:
                if not content:
                    continue

                for pattern in estimate_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        card_data["estimate"] = Decimal(match.group(1))
                        break

                if card_data["estimate"] is not None:
                    break

        cards.append(card_data)

    return cards


def issue_estimates_from_github_project(project_url: str) -> list[Any]:
    estimates = {}
    cards = get_project_cards(project_url, settings.GITHUB_API_TOKEN)
    for card in cards:
        if (issue := card.get("issue")) and (estimate := card.get("estimate")):
            if isinstance(issue, dict) and "html_url" in issue:
                # Classic projects
                issue_url = issue["html_url"]
            elif (
                isinstance(issue, dict)
                and "owner" in issue
                and "repo" in issue
                and "number" in issue
            ):
                issue_url = f"https://github.com/{issue['owner']}/{issue['repo']}/issues/{issue['number']}"
            estimates[issue_url] = Decimal(str(estimate))
    return estimates
