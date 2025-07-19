import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
import pytz

from aicore.llm.providers.base_provider import LlmBaseProvider
from aicore.models_metadata import PricingConfig, HappyHour, DynamicPricing
from aicore.llm.usage import CompletionUsage, UsageInfo
from aicore.llm.config import LlmConfig
from aicore.llm.llm import Llm


@pytest.fixture
def static_pricing_config():
    """Fixture for static pricing configuration"""
    return PricingConfig(
        input=10.0,
        output=20.0,
        cached=5.0,
        cache_write=2.0
    )


@pytest.fixture
def happy_hour_pricing_config():
    """Fixture for pricing config with happy hour"""
    now = datetime.now(pytz.UTC)
    return PricingConfig(
        input=10.0,
        output=20.0,
        happy_hour=HappyHour(
            start=now - timedelta(hours=1),
            finish=now + timedelta(hours=1),
            pricing=PricingConfig(input=5.0, output=10.0)
        )
    )


@pytest.fixture
def dynamic_pricing_config():
    """Fixture for dynamic pricing configuration"""
    return PricingConfig(
        input=10.0,
        output=20.0,
        dynamic=DynamicPricing(
            threshold=1000,
            pricing=PricingConfig(input=8.0, output=15.0)
        )
    )


@pytest.fixture
def mock_llm_config():
    """Fixture for mock LLM configuration"""
    return LlmConfig(
        provider="openai",
        api_key="test_key",
        model="gpt-4"
    )


class TestStaticPricing:
    def test_basic_token_calculation(self, static_pricing_config):
        """Test basic token cost calculation"""
        usage = CompletionUsage(
            prompt_tokens=1000,
            response_tokens=2000
        )
        usage.update_with_pricing(static_pricing_config)
        
        expected_cost = (1000 * 10.0 + 2000 * 20.0) * 1e-6
        assert usage.cost == pytest.approx(expected_cost)

    def test_zero_tokens(self, static_pricing_config):
        """Test edge case with zero tokens"""
        usage = CompletionUsage(
            prompt_tokens=0,
            response_tokens=0
        )
        usage.update_with_pricing(static_pricing_config)
        assert usage.cost == 0.0

    def test_cached_tokens(self, static_pricing_config):
        """Test cached token pricing"""
        usage = CompletionUsage(
            prompt_tokens=1000,
            response_tokens=2000,
            cached_tokens=500
        )
        usage.update_with_pricing(static_pricing_config)
        
        expected_cost = (1000 * 10.0 + 2000 * 20.0 + 500 * 5.0) * 1e-6
        assert usage.cost == pytest.approx(expected_cost)


class TestHappyHourPricing:
    @patch('aicore.llm.usage.datetime')
    def test_active_happy_hour(self, mock_datetime, happy_hour_pricing_config):
        """Test happy hour pricing when active"""
        now = datetime.now(pytz.UTC)
        mock_datetime.now.return_value = now
        
        usage = CompletionUsage(
            prompt_tokens=1000,
            response_tokens=2000
        )
        usage.update_with_pricing(happy_hour_pricing_config)
        
        expected_cost = (1000 * 5.0 + 2000 * 10.0) * 1e-6
        assert usage.cost == pytest.approx(expected_cost)

    @patch('aicore.llm.usage.datetime')
    def test_inactive_happy_hour(self, mock_datetime, happy_hour_pricing_config):
        """Test happy hour pricing when inactive"""
        now = datetime.now(pytz.UTC) + timedelta(hours=2)  # Outside happy hour
        mock_datetime.now.return_value = now
        
        usage = CompletionUsage(
            prompt_tokens=1000,
            response_tokens=2000
        )
        usage.update_with_pricing(happy_hour_pricing_config)
        
        expected_cost = (1000 * 10.0 + 2000 * 20.0) * 1e-6
        assert usage.cost == pytest.approx(expected_cost)

    def test_missing_happy_hour(self, static_pricing_config):
        """Test behavior when happy hour is not configured"""
        usage = CompletionUsage(
            prompt_tokens=1000,
            response_tokens=2000
        )
        usage.update_with_pricing(static_pricing_config)
        
        expected_cost = (1000 * 10.0 + 2000 * 20.0) * 1e-6
        assert usage.cost == pytest.approx(expected_cost)


class TestDynamicPricing:
    def test_below_threshold(self, dynamic_pricing_config):
        """Test pricing below dynamic threshold"""
        usage = CompletionUsage(
            prompt_tokens=500,
            response_tokens=400
        )
        usage.update_with_pricing(dynamic_pricing_config)
        
        expected_cost = (500 * 10.0 + 400 * 20.0) * 1e-6
        assert usage.cost == pytest.approx(expected_cost)

    def test_above_threshold(self, dynamic_pricing_config):
        """Test pricing above dynamic threshold"""
        usage = CompletionUsage(
            prompt_tokens=600,
            response_tokens=500
        )
        usage.update_with_pricing(dynamic_pricing_config)
        
        expected_cost = (600 * 8.0 + 500 * 15.0) * 1e-6
        assert usage.cost == pytest.approx(expected_cost)

    def test_exact_threshold(self, dynamic_pricing_config):
        """Test pricing at exact threshold"""
        usage = CompletionUsage(
            prompt_tokens=1000,
            response_tokens=0
        )
        usage.update_with_pricing(dynamic_pricing_config)
        
        expected_cost = (1000 * 10.0 + 0 * 20.0) * 1e-6
        assert usage.cost == pytest.approx(expected_cost)

    def test_missing_dynamic_config(self, static_pricing_config):
        """Test behavior when dynamic pricing is not configured"""
        usage = CompletionUsage(
            prompt_tokens=1000,
            response_tokens=2000
        )
        usage.update_with_pricing(static_pricing_config)
        
        expected_cost = (1000 * 10.0 + 2000 * 20.0) * 1e-6
        assert usage.cost == pytest.approx(expected_cost)


class TestUsageInfoIntegration:
    def test_single_completion(self, mock_llm_config, static_pricing_config):
        """Test single completion recording"""
        usage_info = UsageInfo.from_pricing_config(static_pricing_config)
        usage_info.record_completion(
            prompt_tokens=1000,
            response_tokens=2000
        )
        
        assert len(usage_info.root) == 1
        assert usage_info.total_tokens == 3000
        expected_cost = (1000 * 10.0 + 2000 * 20.0) * 1e-6
        assert usage_info.total_cost == pytest.approx(expected_cost)

    def test_multiple_completions(self, mock_llm_config, static_pricing_config):
        """Test multiple completions aggregation"""
        usage_info = UsageInfo.from_pricing_config(static_pricing_config)
        usage_info.record_completion(completion_id="id1", prompt_tokens=1000, response_tokens=2000)
        usage_info.record_completion(completion_id="id2", prompt_tokens=500, response_tokens=1000)
        
        assert len(usage_info.root) == 2
        assert usage_info.total_tokens == 4500
        expected_cost = (1500 * 10.0 + 3000 * 20.0) * 1e-6
        assert usage_info.total_cost == pytest.approx(expected_cost)

    def test_cost_calculation(self, mock_llm_config, static_pricing_config):
        """Test total cost calculation"""
        usage_info = UsageInfo.from_pricing_config(static_pricing_config)
        usage_info.record_completion(completion_id="id1", prompt_tokens=1000, response_tokens=2000)
        usage_info.record_completion(completion_id="id2", prompt_tokens=500, response_tokens=1000, cached_tokens=300)
        
        expected_cost = (1500 * 10.0 + 3000 * 20.0 + 300 * 5.0) * 1e-6
        assert usage_info.total_cost == pytest.approx(expected_cost)


class TestLlmIntegration:
    def test_llm_with_pricing(self, mock_llm_config, static_pricing_config):
        """Test LLM integration with pricing config"""
        mock_llm_config.pricing = static_pricing_config

        # Patch validate_config before Llm is initialized
        with patch.object(LlmBaseProvider, 'validate_config', return_value=None):
            llm = Llm(config=mock_llm_config)
            with patch.object(Llm, 'complete', return_value="test response") as mock_complete:
                response = llm.complete("test prompt")
                
                mock_complete.assert_called_once()
                assert response == "test response"
                assert llm.usage.pricing == static_pricing_config

    def test_usage_info_attached(self, mock_llm_config):
        """Test UsageInfo is properly attached to LLM instance"""
        with patch.object(LlmBaseProvider, 'validate_config', return_value=None):
            llm = Llm(config=mock_llm_config)
            assert isinstance(llm.usage, UsageInfo)
            assert llm.usage.pricing is None


class TestEdgeCases:
    def test_negative_tokens(self, static_pricing_config):
        """Test that negative token counts raise an error"""
        with pytest.raises(ValueError, match="Token counts cannot be negative"):
            CompletionUsage(
                prompt_tokens=-100,
                response_tokens=2000
            )

    def test_invalid_dynamic_threshold(self):
        """Test that invalid dynamic threshold raises an error"""
        with pytest.raises(ValueError, match="Dynamic pricing threshold must be positive"):
            PricingConfig(
                input=10.0,
                output=20.0,
                dynamic=DynamicPricing(
                    threshold=0,
                    pricing=PricingConfig(input=8.0, output=15.0)
                )
            )
