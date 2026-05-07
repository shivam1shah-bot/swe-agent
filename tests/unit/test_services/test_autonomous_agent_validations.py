import pytest

from src.services.agents import validations as V


def test_missing_prompt_raises():
    with pytest.raises(ValueError) as exc:
        V.validate_parameters({"repository_url": "https://github.com/razorpay/api"})
    assert "prompt" in str(exc.value).lower()


def test_missing_repository_url_raises():
    with pytest.raises(ValueError) as exc:
        V.validate_parameters({"prompt": "do it"})
    assert "repository_url" in str(exc.value).lower()


def test_invalid_host_raises():
    with pytest.raises(ValueError) as exc:
        V.validate_parameters({
            "prompt": "x",
            "repository_url": "http://gitlab.com/razorpay/api"
        })
    # Must mention invalid GitHub URL
    assert "github" in str(exc.value).lower()


def test_wrong_org_raises():
    with pytest.raises(ValueError) as exc:
        V.validate_parameters({
            "prompt": "x",
            "repository_url": "https://github.com/other/repo"
        })
    assert "razorpay" in str(exc.value).lower()


def test_invalid_repo_name_raises():
    with pytest.raises(ValueError) as exc:
        V.validate_parameters({
            "prompt": "x",
            "repository_url": "https://github.com/razorpay/in*valid"
        })
    assert "invalid repository name" in str(exc.value).lower()


def test_branch_main_not_allowed():
    with pytest.raises(ValueError) as exc:
        V.validate_parameters({
            "prompt": "x",
            "repository_url": "https://github.com/razorpay/api",
            "branch": "main"
        })
    assert "not allowed" in str(exc.value).lower()


def test_branch_master_not_allowed():
    with pytest.raises(ValueError) as exc:
        V.validate_parameters({
            "prompt": "x",
            "repository_url": "https://github.com/razorpay/api",
            "branch": "master"
        })
    assert "not allowed" in str(exc.value).lower()


def test_branch_invalid_chars_not_allowed():
    with pytest.raises(ValueError) as exc:
        V.validate_parameters({
            "prompt": "x",
            "repository_url": "https://github.com/razorpay/api",
            "branch": "feature bad"
        })
    assert "invalid branch name" in str(exc.value).lower()


def test_valid_parameters_pass():
    # Should not raise
    V.validate_parameters({
        "prompt": "do it",
        "repository_url": "https://github.com/razorpay/api",
        "branch": "feature/test-1"
    })


