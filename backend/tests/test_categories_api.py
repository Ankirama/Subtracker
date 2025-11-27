"""
Tests for Categories API endpoints.

Tests cover:
- List categories (default + custom)
- Create custom categories
- Delete custom categories
- Name normalization and validation
- Default category protection
- Duplicate detection
"""

from uuid import uuid4

from app.models.category import Category, DEFAULT_CATEGORIES


class TestGetCategories:
    """Test GET /api/categories - list all categories."""

    def test_get_categories_default_only(self, client, auth_headers):
        """List categories returns all default categories when user has no custom ones."""
        response = client.get("/api/categories", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "categories" in data
        assert "total" in data
        assert data["total"] == len(DEFAULT_CATEGORIES)

        # Check that all default categories are present
        category_names = [cat["name"] for cat in data["categories"]]
        for default_cat in DEFAULT_CATEGORIES.keys():
            assert default_cat in category_names

        # All should be marked as default
        for cat in data["categories"]:
            assert cat["is_default"] is True
            assert cat["id"] is None
            assert cat["user_id"] is None

    def test_get_categories_with_custom(
        self, client, auth_headers, db_session, test_user
    ):
        """List categories includes custom categories along with defaults."""
        # Create custom category
        custom_cat = Category(
            user_id=test_user.id,
            name="custom_test",
            display_name="Custom Test",
            color="purple",
            is_default=False,
        )
        db_session.add(custom_cat)
        db_session.commit()

        response = client.get("/api/categories", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should have defaults + 1 custom
        assert data["total"] == len(DEFAULT_CATEGORIES) + 1

        # Find the custom category
        custom_cats = [cat for cat in data["categories"] if not cat["is_default"]]
        assert len(custom_cats) == 1
        assert custom_cats[0]["name"] == "custom_test"
        assert custom_cats[0]["display_name"] == "Custom Test"
        assert custom_cats[0]["color"] == "purple"
        assert custom_cats[0]["id"] is not None
        assert custom_cats[0]["user_id"] is not None

    def test_get_categories_structure(self, client, auth_headers):
        """Verify category response structure."""
        response = client.get("/api/categories", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check first category has all required fields
        cat = data["categories"][0]
        assert "id" in cat
        assert "name" in cat
        assert "display_name" in cat
        assert "color" in cat
        assert "is_default" in cat
        assert "user_id" in cat

    def test_get_categories_no_auth(self, client):
        """Cannot list categories without authentication."""
        response = client.get("/api/categories")

        assert response.status_code == 403


class TestCreateCategory:
    """Test POST /api/categories - create custom category."""

    def test_create_category_success(self, client, auth_headers):
        """Successfully create a custom category."""
        category_data = {
            "name": "MyCustomCategory",
            "display_name": "My Custom Category",
            "color": "orange",
        }

        response = client.post(
            "/api/categories", headers=auth_headers, json=category_data
        )

        assert response.status_code == 201
        data = response.json()

        # Name should be normalized (lowercase, underscores)
        assert data["name"] == "mycustomcategory"
        assert data["display_name"] == "My Custom Category"
        assert data["color"] == "orange"
        assert data["is_default"] is False
        assert data["id"] is not None
        assert data["user_id"] is not None
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_category_with_spaces(self, client, auth_headers):
        """Category name with spaces gets normalized to underscores."""
        category_data = {
            "name": "My Test Category",
            "display_name": "My Test Category",
            "color": "blue",
        }

        response = client.post(
            "/api/categories", headers=auth_headers, json=category_data
        )

        assert response.status_code == 201
        data = response.json()

        # Spaces should be replaced with underscores and lowercased
        assert data["name"] == "my_test_category"

    def test_create_category_uppercase_normalized(self, client, auth_headers):
        """Uppercase category names are normalized to lowercase."""
        category_data = {
            "name": "UPPERCASE",
            "display_name": "Uppercase Display",
            "color": "green",
        }

        response = client.post(
            "/api/categories", headers=auth_headers, json=category_data
        )

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "uppercase"

    def test_create_category_default_color(self, client, auth_headers):
        """Category created with default color when not specified."""
        category_data = {"name": "NoColor", "display_name": "No Color Category"}

        response = client.post(
            "/api/categories", headers=auth_headers, json=category_data
        )

        assert response.status_code == 201
        data = response.json()

        # Should have default color 'gray'
        assert data["color"] == "gray"

    def test_create_category_duplicate(
        self, client, auth_headers, db_session, test_user
    ):
        """Cannot create duplicate custom category."""
        # Create first category
        existing = Category(
            user_id=test_user.id,
            name="duplicate_test",
            display_name="Duplicate Test",
            color="blue",
        )
        db_session.add(existing)
        db_session.commit()

        # Try to create duplicate
        category_data = {
            "name": "duplicate_test",
            "display_name": "Another Duplicate",
            "color": "red",
        }

        response = client.post(
            "/api/categories", headers=auth_headers, json=category_data
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_create_category_conflicts_with_default(self, client, auth_headers):
        """Cannot create custom category with same name as default category."""
        # Try to create category with default name
        category_data = {
            "name": "streaming",  # Default category
            "display_name": "Custom Streaming",
            "color": "purple",
        }

        response = client.post(
            "/api/categories", headers=auth_headers, json=category_data
        )

        assert response.status_code == 400
        assert "default category" in response.json()["detail"].lower()

    def test_create_category_empty_name(self, client, auth_headers):
        """Cannot create category with empty name."""
        category_data = {"name": "", "display_name": "Empty Name", "color": "blue"}

        response = client.post(
            "/api/categories", headers=auth_headers, json=category_data
        )

        assert response.status_code == 422  # Validation error

    def test_create_category_no_auth(self, client):
        """Cannot create category without authentication."""
        category_data = {"name": "test", "display_name": "Test", "color": "blue"}

        response = client.post("/api/categories", json=category_data)

        assert response.status_code == 403


class TestDeleteCategory:
    """Test DELETE /api/categories/{id} - delete custom category."""

    def test_delete_category_success(self, client, auth_headers, db_session, test_user):
        """Successfully delete a custom category."""
        # Create custom category
        custom_cat = Category(
            user_id=test_user.id,
            name="delete_me",
            display_name="Delete Me",
            color="red",
        )
        db_session.add(custom_cat)
        db_session.commit()
        db_session.refresh(custom_cat)

        category_id = custom_cat.id

        response = client.delete(f"/api/categories/{category_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify category was deleted
        deleted = db_session.query(Category).filter(Category.id == category_id).first()
        assert deleted is None

    def test_delete_category_not_found(self, client, auth_headers):
        """Cannot delete non-existent category."""
        fake_id = uuid4()

        response = client.delete(f"/api/categories/{fake_id}", headers=auth_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_category_other_user(self, client, auth_headers, db_session):
        """Cannot delete another user's category."""
        from app.models.user import User
        from app.security.password import hash_password

        # Create another user
        password_hash, salt = hash_password("otherpass")
        other_user = User(
            email="other@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
        )
        db_session.add(other_user)
        db_session.commit()

        # Create category for other user
        other_cat = Category(
            user_id=other_user.id,
            name="other_category",
            display_name="Other Category",
            color="blue",
        )
        db_session.add(other_cat)
        db_session.commit()
        db_session.refresh(other_cat)

        # Try to delete with current user's auth
        response = client.delete(
            f"/api/categories/{other_cat.id}", headers=auth_headers
        )

        assert response.status_code == 404  # Not found (doesn't belong to user)

    def test_delete_category_no_auth(self, client, db_session, test_user):
        """Cannot delete category without authentication."""
        # Create category
        custom_cat = Category(
            user_id=test_user.id, name="test", display_name="Test", color="blue"
        )
        db_session.add(custom_cat)
        db_session.commit()
        db_session.refresh(custom_cat)

        response = client.delete(f"/api/categories/{custom_cat.id}")

        assert response.status_code == 403


class TestCategoryEdgeCases:
    """Test edge cases and special scenarios."""

    def test_create_category_with_leading_trailing_spaces(self, client, auth_headers):
        """Category name and display name are trimmed."""
        category_data = {
            "name": "  spaced  ",
            "display_name": "  Spaced Display  ",
            "color": "blue",
        }

        response = client.post(
            "/api/categories", headers=auth_headers, json=category_data
        )

        assert response.status_code == 201
        data = response.json()

        # Name should be trimmed and normalized
        assert data["name"] == "spaced"
        # Display name should be trimmed
        assert data["display_name"] == "Spaced Display"

    def test_create_multiple_custom_categories(self, client, auth_headers):
        """Can create multiple custom categories."""
        categories = [
            {"name": "cat1", "display_name": "Category 1", "color": "red"},
            {"name": "cat2", "display_name": "Category 2", "color": "blue"},
            {"name": "cat3", "display_name": "Category 3", "color": "green"},
        ]

        for cat_data in categories:
            response = client.post(
                "/api/categories", headers=auth_headers, json=cat_data
            )
            assert response.status_code == 201

        # Get all categories
        response = client.get("/api/categories", headers=auth_headers)
        data = response.json()

        # Should have defaults + 3 custom
        assert data["total"] == len(DEFAULT_CATEGORIES) + 3

        custom_cats = [cat for cat in data["categories"] if not cat["is_default"]]
        assert len(custom_cats) == 3

    def test_default_categories_count(self, client, auth_headers):
        """Verify correct number of default categories."""
        response = client.get("/api/categories", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        default_cats = [cat for cat in data["categories"] if cat["is_default"]]
        assert len(default_cats) == 14  # Current count of DEFAULT_CATEGORIES

    def test_default_categories_have_expected_fields(self, client, auth_headers):
        """Default categories have proper structure."""
        response = client.get("/api/categories", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check a specific default category
        streaming = next(
            cat for cat in data["categories"] if cat["name"] == "streaming"
        )
        assert streaming["display_name"] == "Streaming"
        assert streaming["color"] == "red"
        assert streaming["is_default"] is True
        assert streaming["id"] is None
        assert streaming["user_id"] is None
        assert streaming["created_at"] is None
        assert streaming["updated_at"] is None
