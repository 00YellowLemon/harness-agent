# AI-Driven UX Process for Rapid MVPs

This process is streamlined for a solo developer leveraging AI to rapidly test new ideas and markets. It eliminates traditional, time-intensive UX steps in favor of outcome-based design, AI-driven hypothesis formulation, and immediate AI-assisted coding.

## 1. Problem Definition & Audience
Instead of manual persona creation and exhaustive journey mapping, quickly define the core problem space.
*   **Identify the Problem:** Clearly state the customer problem, situation, or opportunity.
*   **Identify User Pain Points:** Use AI to help analyze the problem space and synthesize the most critical pain points.
*   **Define Target Audience:** Briefly identify who experiences this problem most acutely.

## 2. AI-Driven Hypothesis Formulation
Leverage AI to formulate clear, testable hypotheses. Distinguish between testing the value of the idea and testing the specific solution.

*   **Value-Proposition Hypothesis:**
    *   *Template:* "I believe that [value proposition] is valuable to [audience]. I will know this is true when I observe [behavioral signal/metric] from early usage."
*   **Solution Hypothesis:**
    *   *Template:* "For [audience] who [need], I believe that [MVP product/feature] will deliver [value]. I will know this is true when [metric] reaches [target] within [timeframe]."
    *   *Note:* Ensure clear criteria are defined for whether data supports, partially supports, or fails to support the hypothesis.

## 3. Risk-Reward Assessment
Evaluate the idea quickly to ensure you are building the right MVP.
*   **Risk:** How costly is it if the hypothesis is wrong (e.g., wasted time, complex infrastructure)?
*   **Reward:** How much value is gained if the hypothesis is correct (e.g., new market validated)?
*   *Action:* Prioritize high-reward ideas. Use the assessment to relentlessly prune features that do not directly test the core hypotheses.

## 4. Define the MVP Core
Skip deep information architecture, storyboards, and competitive audits. Outline just enough structure to guide the AI coding phase.
*   **Create Goal Statement:** A single, focused sentence defining what the MVP must accomplish to validate the hypotheses.
*   **Core User Stories & Edge Cases:** List the absolute minimum user stories required to test the value proposition. Ask the AI to identify critical edge cases that must be handled.
*   **Minimal Flow/Architecture:** Outline the basic data structure and user flow needed for the AI prompt.

## 5. AI-Assisted Coding (Live-Code MVP)
Skip traditional prototyping (e.g., Figma, clickable prototypes) and move directly to building a live-code MVP using agentic coding tools.
*   **Generate MVP Prompt:** Combine your goal statement, user stories, and minimal flow into a comprehensive prompt for your AI coding agent.
*   **Agentic Development:** Work with the AI to build the core functionality. Focus strictly on usability for the core flow—if the usability is poor, the MVP tests the interface, not the idea.
*   **Deploy, Measure, and Learn:** Launch the live-code MVP to yourself or a small test group. Measure real-world behavior against your hypotheses to decide whether to pivot, persevere, or expand.
