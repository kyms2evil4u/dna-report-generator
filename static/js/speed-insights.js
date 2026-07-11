/**
 * Vercel Speed Insights Integration
 * 
 * This script initializes Vercel Speed Insights for the DNA Report Generator.
 * It tracks Core Web Vitals and performance metrics when deployed to Vercel.
 * 
 * The injectSpeedInsights function is imported from the bundled Speed Insights module.
 */

import { injectSpeedInsights } from '/static/js/speed-insights.mjs';

// Initialize Speed Insights when the script loads
injectSpeedInsights();
