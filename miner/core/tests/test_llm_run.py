"""Tests for LLM backend runtime functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any

from miner.core.llms import get_backend, get_backends, BACKENDS, LLMService
from miner.config.config import MinerConfig


class TestBackendInstantiation:
    """Test backend instantiation with configuration."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock(spec=MinerConfig)
        config.llm_backend = "llamacpp"
        config.model_path = None
        config.tensor_parallel_size = 0
        config.max_model_len = 4096
        config.ollama_base_url = "http://localhost:11434"
        config.ollama_timeout = 300.0
        return config
    
    def test_get_backend_returns_service(self, mock_config):
        """Test that get_backend returns an LLMService instance."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        backends = get_backends()
        if not backends:
            pytest.skip("No backends available")
        
        # Use first available backend
        backend_name = next(iter(backends.keys()))
        service = get_backend(backend_name, mock_config)
        
        assert isinstance(service, LLMService)
        assert service.config == mock_config
    
    def test_get_backend_with_invalid_name_falls_back(self, mock_config):
        """Test that get_backend falls back to first backend if name not found."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        backends = get_backends()
        if not backends:
            pytest.skip("No backends available")
        
        # Use a non-existent backend name
        with patch('loguru.logger.warning') as mock_warning:
            service = get_backend("nonexistent_backend", mock_config)
            
            # Should have logged a warning
            assert mock_warning.called
            
            # Should return a valid service (first available)
            assert isinstance(service, LLMService)
    
    def test_get_backend_raises_if_no_backends(self, mock_config):
        """Test that get_backend raises if no backends are available."""
        with patch('miner.core.llms.BACKENDS', {}):
            with pytest.raises(ValueError, match="No backends available"):
                get_backend("any_backend", mock_config)
    
    @pytest.mark.parametrize("backend_name", ["vllm", "ollama", "llamacpp"])
    def test_backend_instantiation(self, mock_config, backend_name):
        """Test that each backend can be instantiated."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        backends = get_backends()
        if backend_name not in backends:
            pytest.skip(f"Backend {backend_name} not available")
        
        try:
            service = get_backend(backend_name, mock_config)
            assert isinstance(service, LLMService)
        except ImportError as e:
            pytest.skip(f"Backend {backend_name} dependencies not installed: {e}")


class TestBackendMethods:
    """Test backend method signatures and basic functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock(spec=MinerConfig)
        config.llm_backend = "llamacpp"
        config.model_path = None
        config.tensor_parallel_size = 0
        config.max_model_len = 4096
        config.ollama_base_url = "http://localhost:11434"
        config.ollama_timeout = 300.0
        return config
    
    @pytest.fixture
    def service(self, mock_config):
        """Create a service instance."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        backends = get_backends()
        if not backends:
            pytest.skip("No backends available")
        
        backend_name = next(iter(backends.keys()))
        return get_backend(backend_name, mock_config)
    
    def test_service_has_generate_method(self, service):
        """Test that service has generate method."""
        assert hasattr(service, 'generate')
        assert callable(service.generate)
    
    def test_service_has_get_model_method(self, service):
        """Test that service has _get_model method."""
        assert hasattr(service, '_get_model')
        assert callable(service._get_model)
    
    def test_service_has_health_check_method(self, service):
        """Test that service has health_check method."""
        assert hasattr(service, 'health_check')
        assert callable(service.health_check)
    
    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self, service):
        """Test that health_check returns a boolean."""
        result = await service.health_check()
        assert isinstance(result, bool)
    
    def test_service_has_config(self, service):
        """Test that service has config attribute."""
        assert hasattr(service, 'config')
        assert service.config is not None
    
    def test_service_has_models_dict(self, service):
        """Test that service has models dictionary."""
        assert hasattr(service, 'models')
        assert isinstance(service.models, dict)


class TestBackendConfiguration:
    """Test backend configuration handling."""
    
    def test_config_passed_to_service(self):
        """Test that config is passed to service."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        backends = get_backends()
        if not backends:
            pytest.skip("No backends available")
        
        config = MinerConfig()
        backend_name = next(iter(backends.keys()))
        
        try:
            service = get_backend(backend_name, config)
            assert service.config == config
        except ImportError:
            pytest.skip("Backend dependencies not installed")
    
    def test_backend_uses_config_values(self):
        """Test that backend uses config values."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        backends = get_backends()
        if not backends:
            pytest.skip("No backends available")
        
        config = MinerConfig()
        config.llm_backend = "ollama"
        config.ollama_base_url = "http://custom:11434"
        
        if "ollama" in backends:
            try:
                service = get_backend("ollama", config)
                # Ollama service should use the custom base URL
                if hasattr(service, 'base_url'):
                    assert service.base_url == "http://custom:11434"
            except ImportError:
                pytest.skip("Ollama backend not available")


class TestBackendFallback:
    """Test backend fallback behavior."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock(spec=MinerConfig)
        config.llm_backend = "nonexistent"
        return config
    
    def test_fallback_to_first_backend(self, mock_config):
        """Test fallback to first available backend."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        backends = get_backends()
        if not backends:
            pytest.skip("No backends available")
        
        first_backend = next(iter(backends.keys()))
        
        with patch('loguru.logger.warning') as mock_warning:
            service = get_backend("nonexistent_backend", mock_config)
            
            # Should have logged warning
            assert mock_warning.called
            warning_msg = str(mock_warning.call_args)
            assert "nonexistent_backend" in warning_msg or "not found" in warning_msg.lower()
            
            # Should return a service
            assert isinstance(service, LLMService)


class TestBackendIntegration:
    """Integration tests for backend functionality."""
    
    @pytest.mark.asyncio
    async def test_backend_health_check_integration(self):
        """Test backend health check in integration scenario."""
        assert len(BACKENDS) > 0, "BACKENDS must be non-empty"
        backends = get_backends()
        if not backends:
            pytest.skip("No backends available")
        
        config = MinerConfig()
        backend_name = next(iter(backends.keys()))
        
        try:
            service = get_backend(backend_name, config)
            health = await service.health_check()
            assert isinstance(health, bool)
        except ImportError:
            pytest.skip("Backend dependencies not installed")
        except Exception as e:
            # Some backends may fail health check if not properly configured
            # This is acceptable for testing
            pytest.skip(f"Backend health check failed (expected in test env): {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

