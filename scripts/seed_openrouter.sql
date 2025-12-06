-- =============================================================================
-- Seed script for OpenRouter provider configuration
--
-- OpenRouter API Documentation: https://openrouter.ai/docs/api/reference/overview
-- Base URL: https://openrouter.ai/api/v1
-- Chat Completions Endpoint: POST /chat/completions
-- =============================================================================

-- First, we need to add 'openrouter' to the provider_type enum if not exists
-- Note: Run this only if the enum doesn't already include 'openrouter'
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'openrouter'
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'providertype')
    ) THEN
        ALTER TYPE providertype ADD VALUE 'openrouter';
    END IF;
END$$;

-- Insert OpenRouter provider
INSERT INTO providers (id, name, type, description, is_active, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'OpenRouter',
    'openrouter',
    'OpenRouter is an API aggregator that provides unified access to multiple LLM providers including OpenAI, Anthropic, Google, Meta, and more. It offers a single API endpoint compatible with the OpenAI API format.',
    true,
    NOW(),
    NOW()
)
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    updated_at = NOW()
RETURNING id;

-- Get the provider ID for subsequent inserts
-- Note: You may need to run this separately and use the actual UUID

-- Insert OpenRouter endpoint
-- Using a CTE to get the provider_id
WITH provider AS (
    SELECT id FROM providers WHERE name = 'OpenRouter' LIMIT 1
)
INSERT INTO endpoints (
    id,
    provider_id,
    name,
    base_url,
    api_version,
    region,
    timeout_connect,
    timeout_read,
    retry_count,
    retry_interval,
    is_default,
    is_active,
    health_status,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    provider.id,
    'OpenRouter API v1',
    'https://openrouter.ai/api/v1',  -- Base URL for OpenRouter API
    'v1',
    'global',  -- OpenRouter is globally distributed
    30,        -- Connection timeout in seconds
    120,       -- Read timeout in seconds
    3,         -- Retry count
    1,         -- Retry interval in seconds
    true,      -- Set as default endpoint
    true,      -- Active
    'healthy', -- Initial health status
    NOW(),
    NOW()
FROM provider
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Popular models available through OpenRouter
-- Note: Prices are approximate and may change. Check https://openrouter.ai/models
-- =============================================================================

WITH provider AS (
    SELECT id FROM providers WHERE name = 'OpenRouter' LIMIT 1
)
INSERT INTO models (
    id,
    provider_id,
    model_id,
    name,
    version,
    type,
    context_window,
    max_output_tokens,
    input_price,
    output_price,
    capabilities,
    status,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    provider.id,
    model_data.model_id,
    model_data.name,
    model_data.version,
    model_data.type::modeltype,
    model_data.context_window,
    model_data.max_output_tokens,
    model_data.input_price,
    model_data.output_price,
    model_data.capabilities::jsonb,
    'available'::modelstatus,
    NOW(),
    NOW()
FROM provider,
(VALUES
    -- OpenAI Models
    ('openai/gpt-4o', 'GPT-4o', '2024-05', 'chat', 128000, 16384, 0.0025, 0.01,
     '{"vision": true, "function_calling": true, "json_mode": true}'),
    ('openai/gpt-4o-mini', 'GPT-4o Mini', '2024-07', 'chat', 128000, 16384, 0.00015, 0.0006,
     '{"vision": true, "function_calling": true, "json_mode": true}'),
    ('openai/gpt-4-turbo', 'GPT-4 Turbo', '2024-04', 'chat', 128000, 4096, 0.01, 0.03,
     '{"vision": true, "function_calling": true, "json_mode": true}'),

    -- Anthropic Models
    ('anthropic/claude-3.5-sonnet', 'Claude 3.5 Sonnet', '20241022', 'chat', 200000, 8192, 0.003, 0.015,
     '{"vision": true, "function_calling": true}'),
    ('anthropic/claude-3-opus', 'Claude 3 Opus', '20240229', 'chat', 200000, 4096, 0.015, 0.075,
     '{"vision": true, "function_calling": true}'),
    ('anthropic/claude-3-haiku', 'Claude 3 Haiku', '20240307', 'chat', 200000, 4096, 0.00025, 0.00125,
     '{"vision": true, "function_calling": true}'),

    -- Google Models
    ('google/gemini-pro-1.5', 'Gemini Pro 1.5', '2024', 'chat', 1000000, 8192, 0.00125, 0.005,
     '{"vision": true, "function_calling": true}'),
    ('google/gemini-flash-1.5', 'Gemini Flash 1.5', '2024', 'chat', 1000000, 8192, 0.000075, 0.0003,
     '{"vision": true, "function_calling": true}'),

    -- Meta Models
    ('meta-llama/llama-3.1-405b-instruct', 'Llama 3.1 405B', '3.1', 'chat', 131072, 4096, 0.003, 0.003,
     '{"function_calling": true}'),
    ('meta-llama/llama-3.1-70b-instruct', 'Llama 3.1 70B', '3.1', 'chat', 131072, 4096, 0.00035, 0.0004,
     '{"function_calling": true}'),
    ('meta-llama/llama-3.1-8b-instruct', 'Llama 3.1 8B', '3.1', 'chat', 131072, 4096, 0.00006, 0.00006,
     '{"function_calling": true}'),

    -- Mistral Models
    ('mistralai/mistral-large', 'Mistral Large', '2024', 'chat', 128000, 4096, 0.002, 0.006,
     '{"function_calling": true}'),
    ('mistralai/mistral-medium', 'Mistral Medium', '2024', 'chat', 32000, 4096, 0.00275, 0.0081,
     '{"function_calling": true}'),
    ('mistralai/mixtral-8x7b-instruct', 'Mixtral 8x7B', 'v0.1', 'chat', 32000, 4096, 0.00024, 0.00024,
     '{"function_calling": true}'),

    -- DeepSeek Models
    ('deepseek/deepseek-chat', 'DeepSeek Chat', 'v2', 'chat', 128000, 4096, 0.00014, 0.00028,
     '{"function_calling": true}'),
    ('deepseek/deepseek-coder', 'DeepSeek Coder', 'v2', 'chat', 128000, 4096, 0.00014, 0.00028,
     '{"code_generation": true}'),

    -- Qwen Models
    ('qwen/qwen-2.5-72b-instruct', 'Qwen 2.5 72B', '2.5', 'chat', 131072, 8192, 0.00035, 0.0004,
     '{"function_calling": true}'),
    ('qwen/qwen-2.5-coder-32b-instruct', 'Qwen 2.5 Coder 32B', '2.5', 'chat', 131072, 8192, 0.00018, 0.00018,
     '{"code_generation": true}'),

    -- Google Gemini 2.5 Pro (Latest)
    ('google/gemini-2.5-pro-preview', 'Gemini 2.5 Pro Preview', '2.5', 'chat', 1048576, 65536, 0.00125, 0.01,
     '{"vision": true, "function_calling": true, "thinking": true, "multimodal": true, "audio": true, "video": true}')
) AS model_data(model_id, name, version, type, context_window, max_output_tokens, input_price, output_price, capabilities)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Verify the configuration
-- =============================================================================

-- Show the created provider
SELECT
    p.id,
    p.name,
    p.type,
    p.is_active,
    COUNT(DISTINCT e.id) as endpoint_count,
    COUNT(DISTINCT m.id) as model_count
FROM providers p
LEFT JOIN endpoints e ON e.provider_id = p.id
LEFT JOIN models m ON m.provider_id = p.id
WHERE p.name = 'OpenRouter'
GROUP BY p.id, p.name, p.type, p.is_active;

-- Show the endpoint
SELECT
    e.name,
    e.base_url,
    e.api_version,
    e.is_default,
    e.health_status
FROM endpoints e
JOIN providers p ON e.provider_id = p.id
WHERE p.name = 'OpenRouter';

-- Show model count by type
SELECT
    m.type,
    COUNT(*) as count
FROM models m
JOIN providers p ON m.provider_id = p.id
WHERE p.name = 'OpenRouter'
GROUP BY m.type;
