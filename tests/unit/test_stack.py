"""Unit tests for kourai_common.stack — default tech stack definitions."""

from __future__ import annotations

import pytest

from kourai_common.stack import (
    DEFAULT_BACKEND,
    DEFAULT_FRONTEND,
    ProjectStack,
    StackLayer,
    get_stack_context,
    looks_like_scaffolding,
)


class TestStackLayer:
    def test_frozen(self) -> None:
        layer = StackLayer("framework", "FastAPI", "0.115+")
        with pytest.raises(AttributeError):
            layer.name = "Django"  # type: ignore[misc]  # ty: ignore[invalid-assignment]

    def test_default_notes(self) -> None:
        layer = StackLayer("orm", "SQLAlchemy", "2.0+")
        assert layer.notes == ""

    def test_notes_set(self) -> None:
        layer = StackLayer("orm", "SQLAlchemy", "2.0+", "mapped_column style")
        assert layer.notes == "mapped_column style"


class TestProjectStack:
    def test_frozen(self) -> None:
        with pytest.raises(AttributeError):
            DEFAULT_BACKEND.name = "changed"  # type: ignore[misc]  # ty: ignore[invalid-assignment]

    def test_to_prompt_context_contains_name(self) -> None:
        ctx = DEFAULT_BACKEND.to_prompt_context()
        assert "Python Backend" in ctx

    def test_to_prompt_context_contains_layers(self) -> None:
        ctx = DEFAULT_BACKEND.to_prompt_context()
        assert "FastAPI" in ctx
        assert "SQLAlchemy" in ctx
        assert "pytest" in ctx
        assert "ruff" in ctx

    def test_to_prompt_context_includes_notes(self) -> None:
        ctx = DEFAULT_BACKEND.to_prompt_context()
        assert "app factory pattern" in ctx

    def test_frontend_to_prompt_context(self) -> None:
        ctx = DEFAULT_FRONTEND.to_prompt_context()
        assert "React" in ctx
        assert "Vite" in ctx
        assert "TypeScript" in ctx
        assert "TanStack Query" in ctx

    def test_custom_stack(self) -> None:
        stack = ProjectStack(
            name="Minimal",
            layers=(StackLayer("framework", "Flask", "3.0+"),),
        )
        ctx = stack.to_prompt_context()
        assert "Minimal" in ctx
        assert "Flask" in ctx


class TestDefaultStacks:
    def test_backend_has_expected_categories(self) -> None:
        categories = {layer.category for layer in DEFAULT_BACKEND.layers}
        assert "framework" in categories
        assert "orm" in categories
        assert "testing" in categories
        assert "linting" in categories

    def test_frontend_has_expected_categories(self) -> None:
        categories = {layer.category for layer in DEFAULT_FRONTEND.layers}
        assert "framework" in categories
        assert "bundler" in categories
        assert "language" in categories


class TestGetStackContext:
    def test_contains_both_stacks(self) -> None:
        ctx = get_stack_context()
        assert "Python Backend" in ctx
        assert "React Frontend" in ctx

    def test_contains_header(self) -> None:
        ctx = get_stack_context()
        assert "Default Tech Stack" in ctx

    def test_references_templates(self) -> None:
        ctx = get_stack_context()
        assert "templates/backend/" in ctx
        assert "templates/frontend/" in ctx

    def test_custom_stacks(self) -> None:
        custom = ProjectStack(
            name="Django Backend",
            layers=(StackLayer("framework", "Django", "5.2+"),),
        )
        ctx = get_stack_context(backend=custom)
        assert "Django Backend" in ctx
        assert "Django" in ctx
        # Frontend should still be default
        assert "React Frontend" in ctx


class TestLooksLikeScaffolding:
    @pytest.mark.parametrize(
        "text",
        [
            "build me a todo app",
            "create a new REST API",
            "scaffold a project for tracking expenses",
            "I want to set up a new app",
            "initialize a blog platform",
            "make me a dashboard",
        ],
    )
    def test_positive(self, text: str) -> None:
        assert looks_like_scaffolding(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "fix the bug in auth.py",
            "refactor the database module",
            "add a logout button",
            "what does this function do",
            "run the tests",
        ],
    )
    def test_negative(self, text: str) -> None:
        assert looks_like_scaffolding(text) is False
