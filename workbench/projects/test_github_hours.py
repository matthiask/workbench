from django.test import TestCase

from workbench.projects.github import extract_project_info


class GitHubHoursTestCase(TestCase):
    """Tests for GitHub hours integration."""

    def setUp(self):
        """Set up test data."""
        self.test_token = "test_github_token"

    def test_extract_project_info(self):
        """Test extracting project information from different URL formats."""
        # Test classic project URL
        owner, repo, number = extract_project_info(
            "https://github.com/acme/project/projects/1"
        )
        self.assertEqual(owner, "acme")
        self.assertEqual(repo, "project")
        self.assertEqual(number, "1")

        # Test organization project URL
        owner, repo, number = extract_project_info(
            "https://github.com/orgs/acme/projects/2"
        )
        self.assertEqual(owner, "acme")
        self.assertIsNone(repo)
        self.assertEqual(number, "2")

        # Test user project URL
        owner, repo, number = extract_project_info(
            "https://github.com/users/johndoe/projects/3"
        )
        self.assertEqual(owner, "johndoe")
        self.assertIsNone(repo)
        self.assertEqual(number, "3")

        # Test invalid URL
        owner, repo, number = extract_project_info("https://example.com/invalid/url")
        self.assertIsNone(owner)
        self.assertIsNone(repo)
        self.assertIsNone(number)
