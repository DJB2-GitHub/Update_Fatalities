/**
 * ============================================================================
 * ai_provider_payload_enhancer.js
 * ============================================================================
 * 
 * DESCRIPTION:
 * This module provides a utility function `getPayloadEnhancer(provider)` that 
 * returns specific, pre-written instructional text designed to be injected 
 * into an AI system prompt or instructions. 
 * 
 * PURPOSE:
 * When building agentic applications or automating code generation, you often
 * need to instruct an AI coding assistant (like Google Antigravity) on exactly 
 * how to enable "live web search" or "grounding" for different API providers.
 * Because the implementation details vary wildly between providers (e.g., Gemini 
 * uses `google_search`, OpenRouter uses `openrouter:web_search`), this function 
 * centralizes those instructions.
 * 
 * WHEN TO USE THIS FUNCTION:
 * - When dynamically constructing a System Prompt or Persona for an AI coding agent.
 * - When you are about to ask an AI to write or modify API payload code, and 
 *   you want to guarantee it includes the correct syntax for enabling web search.
 * - To ensure consistency across your applications so that "live internet access" 
 *   is requested correctly regardless of the backend AI service.
 * 
 * ============================================================================
 * EXAMPLE USAGE IN A PERSONA/PROMPT CONSTRUCTION:
 * ============================================================================
 * 
 * const { getPayloadEnhancer } = require('./ai_provider_payload_enhancer.js');
 * 
 * const currentProvider = 'gemini'; // This might come from your app's config
 * const searchInstruction = getPayloadEnhancer(currentProvider);
 * 
 * // 1. Defining the Persona/Prompt
 * const systemPersona = `
 * You are an expert API integrations developer.
 * Your task is to update our existing API connection code to support new features.
 * 
 * CRITICAL REQUIREMENT:
 * ${searchInstruction}
 * 
 * Please generate the updated Python code for the request.
 * `;
 * 
 * // 2. Resulting Prompt Sent to the AI (if provider was 'gemini'):
 * /*
 * You are an expert API integrations developer.
 * Your task is to update our existing API connection code to support new features.
 * 
 * CRITICAL REQUIREMENT:
 * Please update the API payload in the code to inject "tools": [{"google_search": {}}] into the request. I want to officially activate Google Search Grounding for the API calls so the model has full, live access to Google Search to retrieve real-time records (like AWM and VWMA) on the fly, just like the web interface does.
 * 
 * Please generate the updated Python code for the request.
 * *\/
 * ============================================================================
 */

/**
 * Returns the exact instructions needed to configure web search grounding
 * for the specified AI provider.
 * 
 * @param {string} provider - The target AI provider ('gemini', 'openrouter', 'deepseek')
 * @returns {string} The text string containing the provider-specific instructions
 */
function getPayloadEnhancer(provider) {
    if (!provider) {
        return 'No provider specified.';
    }

    const normalizedProvider = provider.toLowerCase().trim();

    switch (normalizedProvider) {
        case 'gemini':
        case 'google':
            return 'Please update the API payload in the code to inject "tools": [{"google_search": {}}] into the request. I want to officially activate Google Search Grounding for the API calls so the model has full, live access to Google Search to retrieve real-time records (like AWM and VWMA) on the fly, just like the web interface does.';
            
        case 'openrouter':
            return 'Please update the OpenRouter API request payload to enable live web search capabilities. Inject the OpenRouter web search tool into the tools array by adding: "tools": [{"type": "openrouter:web_search", "parameters": {"engine": "auto"}}]. This will give the model live internet access to retrieve real-time records (like AWM and VWMA) on the fly.';
            
        case 'deepseek':
            return 'Please update our DeepSeek API integration to support live web search so the model can retrieve real-time records (like AWM and VWMA) on the fly. Since DeepSeek\'s standard API requires client-side tool execution, please define a web search function in the tools array and write the logic to execute the search and feed the results back into the model\'s context.';
            
        default:
            return `Provider '${provider}' is not fully supported for this instruction. Please use 'gemini', 'openrouter', or 'deepseek'.`;
    }
}

// Support CommonJS export for Node.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { getPayloadEnhancer };
}

// ---------------------------------------------------------
// DIRECT EXECUTION TEST BLOCK
// ---------------------------------------------------------
// If you run this file directly via `node ai_provider_payload_enhancer.js`, 
// it will output an example to the console.
if (typeof require !== 'undefined' && require.main === module) {
    console.log("--- TEST EXECUTION ---");
    const testProvider = 'openrouter';
    const instruction = getPayloadEnhancer(testProvider);
    
    const examplePrompt = `System Persona:\nYou are a coding assistant.\n\nTask:\n${instruction}`;
    console.log(`\nProvider Tested: ${testProvider}\n`);
    console.log("Resulting Generated Prompt:");
    console.log("--------------------------------------------------");
    console.log(examplePrompt);
    console.log("--------------------------------------------------");
}
