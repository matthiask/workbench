from unittest.mock import MagicMock, patch

from django.test import TestCase

from workbench.projects.github import _get_project_v2_cards


class GitHubFieldExtractionTestCase(TestCase):
    """Test extracting hour estimates from various GitHub project field types."""

    def create_field_response(self, field_data):
        """Helper to create a GraphQL response with project fields."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": {
                "organization": {
                    "projectV2": {
                        "id": "proj_123",
                        "title": "Test Project",
                        "fields": {"nodes": field_data},
                    }
                }
            }
        }
        return response

    def create_items_response(self, items_data):
        """Helper to create a GraphQL response with project items/cards."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": {"node": {"items": {"nodes": items_data}}}
        }
        return response

    @patch("workbench.projects.github.requests.post")
    def test_extract_hours_from_number_field(self, mock_post):
        """Test extracting hours from number fields with different naming patterns."""
        # Create field data with different naming patterns
        field_data = [
            {"id": "field_1", "name": "Hours"},
            {"id": "field_2", "name": "Estimated Time"},
            {"id": "field_3", "name": "Duration (hours)"},
            {"id": "field_4", "name": "Story Points"},  # Should be ignored
        ]

        # Create item data with values for each field
        items_data = [
            {
                "id": "item_1",
                "content": {
                    "number": 1,
                    "title": "Task with Hours field",
                    "url": "https://github.com/acme/repo/issues/1",
                    "repository": {"name": "repo", "owner": {"login": "acme"}},
                },
                "fieldValues": {
                    "nodes": [
                        {"field": {"id": "field_1", "name": "Hours"}, "number": 3.5}
                    ]
                },
            },
            {
                "id": "item_2",
                "content": {
                    "number": 2,
                    "title": "Task with Estimated Time field",
                    "url": "https://github.com/acme/repo/issues/2",
                    "repository": {"name": "repo", "owner": {"login": "acme"}},
                },
                "fieldValues": {
                    "nodes": [
                        {
                            "field": {"id": "field_2", "name": "Estimated Time"},
                            "number": 5.0,
                        }
                    ]
                },
            },
            {
                "id": "item_3",
                "content": {
                    "number": 3,
                    "title": "Task with Duration field",
                    "url": "https://github.com/acme/repo/issues/3",
                    "repository": {"name": "repo", "owner": {"login": "acme"}},
                },
                "fieldValues": {
                    "nodes": [
                        {
                            "field": {"id": "field_3", "name": "Duration (hours)"},
                            "number": 8.0,
                        }
                    ]
                },
            },
            {
                "id": "item_4",
                "content": {
                    "number": 4,
                    "title": "Task with Story Points field (should be ignored)",
                    "url": "https://github.com/acme/repo/issues/4",
                    "repository": {"name": "repo", "owner": {"login": "acme"}},
                },
                "fieldValues": {
                    "nodes": [
                        {
                            "field": {"id": "field_4", "name": "Story Points"},
                            "number": 5.0,
                        }
                    ]
                },
            },
        ]

        # Set up response sequence
        mock_post.side_effect = [
            self.create_field_response(field_data),
            self.create_items_response(items_data),
        ]

        # Call the function being tested
        cards = _get_project_v2_cards(
            "acme", "1", {"Authorization": "token test_token"}
        )

        # Verify the results
        self.assertEqual(len(cards), 4)

        # Check individual cards
        self.assertEqual(cards[0]["estimate"], 3.5)
        self.assertEqual(cards[0]["estimate_field"], "hours")

        self.assertEqual(cards[1]["estimate"], 5.0)
        self.assertEqual(cards[1]["estimate_field"], "estimated time")

        self.assertEqual(cards[2]["estimate"], 8.0)
        self.assertEqual(cards[2]["estimate_field"], "duration (hours)")

        # Story Points field should not be extracted as hours
        self.assertIsNone(cards[3]["estimate"])
        self.assertNotIn("estimate_field", cards[3])

    @patch("workbench.projects.github.requests.post")
    def test_fallback_to_issue_content(self, mock_post):
        """Test fallback to parsing hour estimates from issue title/body."""
        # Create field data with no hour-related fields
        field_data = [
            {"id": "field_1", "name": "Status"},
            {"id": "field_2", "name": "Priority"},
        ]

        # Create item data with hour estimates in title/body
        items_data = [
            {
                "id": "item_1",
                "content": {
                    "number": 1,
                    "title": "Task with estimate: 3.5 hours",
                    "body": "Regular task description",
                    "url": "https://github.com/acme/repo/issues/1",
                    "repository": {"name": "repo", "owner": {"login": "acme"}},
                },
                "fieldValues": {
                    "nodes": [
                        {
                            "field": {"id": "field_1", "name": "Status"},
                            "name": "In Progress",
                        }
                    ]
                },
            },
            {
                "id": "item_2",
                "content": {
                    "number": 2,
                    "title": "Regular task title",
                    "body": "Task details with Hours: 5",
                    "url": "https://github.com/acme/repo/issues/2",
                    "repository": {"name": "repo", "owner": {"login": "acme"}},
                },
                "fieldValues": {
                    "nodes": [
                        {"field": {"id": "field_2", "name": "Priority"}, "name": "High"}
                    ]
                },
            },
            {
                "id": "item_3",
                "content": {
                    "number": 3,
                    "title": "8 hours implementation task",
                    "body": "Task with hours in title",
                    "url": "https://github.com/acme/repo/issues/3",
                    "repository": {"name": "repo", "owner": {"login": "acme"}},
                },
                "fieldValues": {"nodes": []},
            },
        ]

        # Set up response sequence
        mock_post.side_effect = [
            self.create_field_response(field_data),
            self.create_items_response(items_data),
        ]

        # Call the function being tested
        cards = _get_project_v2_cards(
            "acme", "1", {"Authorization": "token test_token"}
        )

        # Verify the results
        self.assertEqual(len(cards), 3)

        # Check individual cards
        self.assertEqual(cards[0]["estimate"], 3.5)
        self.assertEqual(cards[1]["estimate"], 5.0)
        self.assertEqual(cards[2]["estimate"], 8.0)

    @patch("workbench.projects.github.requests.post")
    def test_multiple_number_fields(self, mock_post):
        """Test extraction when an item has multiple number fields."""
        # Create field data with multiple hour-related fields
        field_data = [
            {"id": "field_1", "name": "Hours"},
            {"id": "field_2", "name": "Time Remaining"},
        ]

        # Create item data with multiple number fields
        items_data = [
            {
                "id": "item_1",
                "content": {
                    "number": 1,
                    "title": "Task with multiple hour fields",
                    "url": "https://github.com/acme/repo/issues/1",
                    "repository": {"name": "repo", "owner": {"login": "acme"}},
                },
                "fieldValues": {
                    "nodes": [
                        {"field": {"id": "field_1", "name": "Hours"}, "number": 10.0},
                        {
                            "field": {"id": "field_2", "name": "Time Remaining"},
                            "number": 5.0,
                        },
                    ]
                },
            }
        ]

        # Set up response sequence
        mock_post.side_effect = [
            self.create_field_response(field_data),
            self.create_items_response(items_data),
        ]

        # Call the function being tested
        cards = _get_project_v2_cards(
            "acme", "1", {"Authorization": "token test_token"}
        )

        # Verify that it uses the first matching field it finds
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["estimate"], 10.0)
        self.assertEqual(cards[0]["estimate_field"], "hours")

    @patch("workbench.projects.github.requests.post")
    def test_empty_field_values(self, mock_post):
        """Test handling of empty or null field values."""
        # Create field data with hour-related fields
        field_data = [{"id": "field_1", "name": "Hours"}]

        # Create item data with empty field values
        items_data = [
            {
                "id": "item_1",
                "content": {
                    "number": 1,
                    "title": "Task with empty field",
                    "url": "https://github.com/acme/repo/issues/1",
                    "repository": {"name": "repo", "owner": {"login": "acme"}},
                },
                "fieldValues": {
                    "nodes": [
                        {
                            "field": {"id": "field_1", "name": "Hours"},
                            # Field with null or missing number value should be handled
                        }
                    ]
                },
            },
            {
                "id": "item_2",
                "content": {
                    "number": 2,
                    "title": "Task with no field values",
                    "url": "https://github.com/acme/repo/issues/2",
                    "repository": {"name": "repo", "owner": {"login": "acme"}},
                },
                "fieldValues": {"nodes": []},
            },
        ]

        # Set up response sequence
        mock_post.side_effect = [
            self.create_field_response(field_data),
            self.create_items_response(items_data),
        ]

        # Call the function being tested - should not raise exceptions
        cards = _get_project_v2_cards(
            "acme", "1", {"Authorization": "token test_token"}
        )

        # Verify that cards are still returned with null estimates
        self.assertEqual(len(cards), 2)
        self.assertIsNone(cards[0]["estimate"])
        self.assertIsNone(cards[1]["estimate"])
