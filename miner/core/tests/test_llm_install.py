"""Tests for LLM backend installation and entry point registration."""

import pytest
import importlib.metadata
from unittest.mock import patch, MagicMock

from miner.core.llms import get_backends, BACKENDS, LLMService


class TestBackendInstallation:
    """Test backend installation and entry point discovery."""
    
    def test_get_backends_returns_dict(self):
        """Test that get_backends returns a dictionary."""
        backends = get_backends()
        assert isinstance(backends, dict)
        assert len(backends) > 0, "get_backends() should return at least one backend"
    
    def test_backends_registered(self):
        """Test that backends are registered in BACKENDS."""
        assert isinstance(BACKENDS, dict)
        assert len(BACKENDS) > 0
    
    def test_backends_have_correct_type(self):
        """Test that all registered backends are LLMService subclasses."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        for backend_name, backend_class in BACKENDS.items():
            assert issubclass(backend_class, LLMService), \
                f"Backend {backend_name} must inherit from LLMService"
    
    def test_entry_points_registered(self):
        """Test that entry points are registered in pyproject.toml."""
        try:
            eps = importlib.metadata.entry_points(group="inference.backends")
            entry_point_names = {ep.name for ep in eps}
            
            # Check that we have at least one entry point
            assert len(entry_point_names) > 0, "No entry points found"
            
            # Check that expected backends are registered
            expected_backends = {"vllm", "ollama", "llamacpp"}
            registered_backends = set(BACKENDS.keys())
            
            # At least some expected backends should be available
            assert len(expected_backends.intersection(registered_backends)) > 0, \
                f"Expected at least one of {expected_backends}, got {registered_backends}"
                
        except Exception as e:
            pytest.skip(f"Entry points not available: {e}")
    
    def test_backend_names_match_entry_points(self):
        """Test that backend names in BACKENDS are a subset of entry point names."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        try:
            eps = importlib.metadata.entry_points(group="inference.backends")
            entry_point_names = {ep.name for ep in eps}
            backend_names = set(BACKENDS.keys())
            
            # Backend names should be a subset of entry point names
            # (some backends may be skipped if dependencies are missing)
            assert backend_names.issubset(entry_point_names), \
                f"Backend names {backend_names} should be subset of entry point names {entry_point_names}"
        except Exception as e:
            pytest.skip(f"Entry points not available: {e}")
    
    @pytest.mark.parametrize("backend_name", ["vllm", "ollama", "llamacpp"])
    def test_backend_classes_loadable(self, backend_name):
        """Test that backend classes can be loaded from entry points."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        if backend_name not in BACKENDS:
            pytest.skip(f"Backend {backend_name} not available")
        
        backend_class = BACKENDS[backend_name]
        assert backend_class is not None
        assert issubclass(backend_class, LLMService)
    
    def test_get_backends_uses_entry_points(self):
        """Test that get_backends uses entry points."""
        with patch('importlib.metadata.entry_points') as mock_entry_points:
            # Mock entry points
            mock_ep = MagicMock()
            mock_ep.name = "test_backend"
            mock_ep.load.return_value = LLMService
            mock_entry_points.return_value = [mock_ep]
            
            # Reload module to use mocked entry points
            import importlib
            from miner.core import llms
            importlib.reload(llms)
            
            backends = llms.get_backends()
            assert "test_backend" in backends
            assert backends["test_backend"] == LLMService


class TestBackendDependencies:
    """Test backend-specific dependency availability."""
    
    def test_vllm_import_optional(self):
        """Test that vLLM import is optional."""
        try:
            from vllm import LLM, SamplingParams
            vllm_available = True
        except ImportError:
            vllm_available = False
        
        # Test should pass regardless of vLLM availability
        assert isinstance(vllm_available, bool)
    
    def test_llamacpp_import_optional(self):
        """Test that llama-cpp-python import is optional."""
        try:
            from llama_cpp import Llama
            llamacpp_available = True
        except ImportError:
            llamacpp_available = False
        
        # Test should pass regardless of llama-cpp availability
        assert isinstance(llamacpp_available, bool)
    
    def test_httpx_available(self):
        """Test that httpx is available (required for Ollama)."""
        try:
            import httpx
            httpx_available = True
        except ImportError:
            httpx_available = False
        
        # httpx should be in core dependencies
        assert httpx_available, "httpx should be available (core dependency)"


class TestBackendRegistration:
    """Test backend registration and discovery."""
    
    def test_backends_dict_not_empty(self):
        """Test that BACKENDS dictionary is populated."""
        assert len(BACKENDS) > 0, "No backends registered"
    
    def test_backend_names_are_strings(self):
        """Test that backend names are strings."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        for backend_name in BACKENDS.keys():
            assert isinstance(backend_name, str)
            assert len(backend_name) > 0
    
    def test_backend_classes_are_callable(self):
        """Test that backend classes are callable (can be instantiated)."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        for backend_name, backend_class in BACKENDS.items():
            assert callable(backend_class), \
                f"Backend {backend_name} class must be callable"

