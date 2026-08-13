/**
 * Executive Succession Planning — Cultural Calibration Profiles
 * 
 * Based on GLOBE (Global Leadership and Organizational Behavior Effectiveness)
 * research clusters and Hofstede cultural dimensions.
 * 
 * Each profile defines:
 *   - GLOBE cluster & Hofstede scores
 *   - Layer 2 Cultural Flex weight adjustments
 *   - Layer 3 Sector-specific additions
 *   - Modified threshold minimums
 *   - Additional region-specific criteria
 */

const CULTURAL_PROFILES = {

    // =========================================================================
    // ANGLO (US, UK, Australia, Canada, New Zealand)
    // =========================================================================
    "Anglo_US": {
        label: "Anglo — United States",
        globe_cluster: "Anglo",
        country: "US",
        hofstede: {
            power_distance: 40,
            individualism: 91,
            masculinity: 62,
            uncertainty_avoidance: 46,
            long_term_orientation: 26,
            indulgence: 68
        },
        cultural_context: "Low power distance, high individualism. Results-driven meritocracy. Direct communication style. Individual achievement valued over group harmony. Innovation and disruption celebrated.",
        weight_adjustments: {
            strategic_vision: 0, integrity: 0, cognitive_ability: 0,
            resilience: 0, results_orientation: 0,
            emotional_intelligence: 0, adaptability: 0, self_awareness: 0,
            learning_agility: 0, executive_presence: 0,
            decisiveness: 0, energy_drive: 0,
            industry_expertise: 0, functional_excellence: 0, financial_acumen: 0,
            digital_fluency: 0, global_perspective: 0, talent_development: 0,
            stakeholder_management: 0, board_governance: 0,
            crisis_leadership: 0, innovation_leadership: 0, change_management: 0,
            customer_centricity: 0, operational_excellence: 0
        },
        base_weights: {
            strategic_vision: 9, integrity: 10, cognitive_ability: 8,
            resilience: 8, results_orientation: 8,
            emotional_intelligence: 7, adaptability: 7, self_awareness: 6,
            learning_agility: 7, executive_presence: 8,
            decisiveness: 7, energy_drive: 6,
            industry_expertise: 7, functional_excellence: 6, financial_acumen: 7,
            digital_fluency: 6, global_perspective: 7, talent_development: 6,
            stakeholder_management: 8, board_governance: 7,
            crisis_leadership: 7, innovation_leadership: 6, change_management: 6,
            customer_centricity: 6, operational_excellence: 6
        },
        thresholds: {
            strategic_vision: 7, integrity: 8, cognitive_ability: 6,
            resilience: 7, results_orientation: 7
        },
        additional_criteria: [],
        notes: "Standard Anglo/Western executive profile. Direct communication, individual accountability, shareholder-first governance."
    },

    // =========================================================================
    // MIDDLE EAST (Iran, UAE, Saudi Arabia, Kuwait, Qatar, Egypt, Turkey)
    // =========================================================================
    "Middle_East_IR": {
        label: "Middle East — Iran",
        globe_cluster: "Middle_East",
        country: "IR",
        hofstede: {
            power_distance: 58,
            individualism: 41,
            masculinity: 43,
            uncertainty_avoidance: 59,
            long_term_orientation: 14,
            indulgence: 40
        },
        cultural_context: "High power distance with collective decision-making. Relationships precede transactions. Islamic business principles (halal commerce, no riba/interest). Hierarchical authority respected. Consensus built through personal networks and trust. Sanctions environment requires exceptional political navigation. Arabic/Farsi language capability critical for credibility.",
        weight_adjustments: {
            strategic_vision: 0, integrity: +0.05, cognitive_ability: -0.05,
            resilience: +0.1, results_orientation: -0.05,
            emotional_intelligence: +0.1, adaptability: +0.1, self_awareness: 0,
            learning_agility: -0.05, executive_presence: -0.05,
            decisiveness: -0.05, energy_drive: 0,
            industry_expertise: +0.05, functional_excellence: 0, financial_acumen: 0,
            digital_fluency: -0.1, global_perspective: +0.1, talent_development: 0,
            stakeholder_management: +0.15, board_governance: -0.1,
            crisis_leadership: +0.1, innovation_leadership: -0.1, change_management: -0.05,
            customer_centricity: 0, operational_excellence: 0
        },
        base_weights: {
            strategic_vision: 9, integrity: 10, cognitive_ability: 7,
            resilience: 9, results_orientation: 7,
            emotional_intelligence: 9, adaptability: 9, self_awareness: 7,
            learning_agility: 6, executive_presence: 7,
            decisiveness: 6, energy_drive: 7,
            industry_expertise: 8, functional_excellence: 6, financial_acumen: 7,
            digital_fluency: 5, global_perspective: 9, talent_development: 7,
            stakeholder_management: 10, board_governance: 5,
            crisis_leadership: 8, innovation_leadership: 5, change_management: 6,
            customer_centricity: 7, operational_excellence: 7
        },
        thresholds: {
            strategic_vision: 6, integrity: 8, cognitive_ability: 6,
            resilience: 7, results_orientation: 6
        },
        additional_criteria: [
            {
                id: "relationship_networks",
                name: "Relationship Networks",
                weight: 10,
                description: "Depth of personal/tribal/business network across government and private sector. Wasta (influence through connections) is the primary business mechanism.",
                threshold: 7
            },
            {
                id: "cultural_faith_ethics",
                name: "Cultural & Faith Ethics",
                weight: 9,
                description: "Understanding of Islamic business principles (halal commerce, mudarabah, no riba). Respect for religious observances (Friday prayers, Ramadan scheduling, Hajj leave).",
                threshold: 6
            },
            {
                id: "hierarchical_respect",
                name: "Hierarchical Respect",
                weight: 9,
                description: "Ability to navigate authority structures. Deference to seniority and position. Understanding that direct challenge to authority is culturally inappropriate.",
                threshold: 7
            },
            {
                id: "political_savvy",
                name: "Political Savvy",
                weight: 9,
                description: "Navigation of sanctions regime (OFAC, EU), IRGC-adjacent entity awareness, government relationship management, factional politics understanding.",
                threshold: 7
            },
            {
                id: "coalition_building",
                name: "Coalition Building",
                weight: 8,
                description: "Ability to build consensus across tribal, factional, and family networks. Patient relationship cultivation over months/years before business transactions.",
                threshold: 6
            },
            {
                id: "sanctions_compliance",
                name: "Sanctions & Compliance Navigation",
                weight: 8,
                description: "Deep knowledge of OFAC SDN list, EU restrictive measures, JCPOA implications, dual-use technology restrictions, financial routing constraints.",
                threshold: 7
            },
            {
                id: "language_capability",
                name: "Language Capability (Farsi/Arabic)",
                weight: 7,
                description: "Professional working proficiency in Farsi preferred. Arabic useful for broader regional engagement. English alone insufficient for trust-building.",
                threshold: 5
            }
        ],
        notes: "Iran presents unique challenges: active sanctions regime, complex factional politics, Islamic business principles. Relationship depth is non-negotiable — transactions follow trust, not vice versa. Western-trained executives often fail by applying transactional approaches."
    },

    "Middle_East_AE": {
        label: "Middle East — UAE",
        globe_cluster: "Middle_East",
        country: "AE",
        hofstede: {
            power_distance: 90,
            individualism: 25,
            masculinity: 50,
            uncertainty_avoidance: 80,
            long_term_orientation: 23,
            indulgence: 26
        },
        cultural_context: "Very high power distance, group collectivism. Rapidly modernizing but traditional social structures persist. Vision 2030-style transformation ethos. Sovereign wealth fund relationships critical. Emiratisation workforce policies. Arabic essential, English widely used in business.",
        weight_adjustments: {
            strategic_vision: +0.05, integrity: +0.05, cognitive_ability: 0,
            resilience: +0.05, results_orientation: 0,
            emotional_intelligence: +0.1, adaptability: +0.1, self_awareness: 0,
            learning_agility: 0, executive_presence: +0.05,
            decisiveness: -0.05, energy_drive: 0,
            industry_expertise: 0, functional_excellence: 0, financial_acumen: +0.05,
            digital_fluency: 0, global_perspective: +0.1, talent_development: +0.05,
            stakeholder_management: +0.15, board_governance: -0.05,
            crisis_leadership: 0, innovation_leadership: +0.05, change_management: 0,
            customer_centricity: 0, operational_excellence: 0
        },
        base_weights: {
            strategic_vision: 10, integrity: 10, cognitive_ability: 8,
            resilience: 9, results_orientation: 8,
            emotional_intelligence: 9, adaptability: 9, self_awareness: 7,
            learning_agility: 7, executive_presence: 9,
            decisiveness: 6, energy_drive: 7,
            industry_expertise: 7, functional_excellence: 6, financial_acumen: 8,
            digital_fluency: 7, global_perspective: 9, talent_development: 7,
            stakeholder_management: 10, board_governance: 6,
            crisis_leadership: 7, innovation_leadership: 7, change_management: 7,
            customer_centricity: 7, operational_excellence: 7
        },
        thresholds: {
            strategic_vision: 7, integrity: 8, cognitive_ability: 6,
            resilience: 7, results_orientation: 6
        },
        additional_criteria: [
            {
                id: "relationship_networks",
                name: "Relationship Networks",
                weight: 10,
                description: "Access to royal family / ruling family networks, sovereign wealth fund relationships (ADIA, Mubadala, ADQ). Personal connections to key decision-makers.",
                threshold: 7
            },
            {
                id: "cultural_faith_ethics",
                name: "Cultural & Faith Ethics",
                weight: 8,
                description: "Islamic finance knowledge (sukuk, murabaha). Respect for cultural norms. Understanding of Emiratisation policies and national identity.",
                threshold: 6
            },
            {
                id: "hierarchical_respect",
                name: "Hierarchical Respect",
                weight: 9,
                description: "Deference to ruling family and government authority. Understanding that government relationships are paramount.",
                threshold: 7
            },
            {
                id: "political_savvy",
                name: "Political Savvy",
                weight: 8,
                description: "Navigation of GCC politics, understanding of Vision strategies, government procurement processes.",
                threshold: 6
            }
        ],
        notes: "UAE is more modernized than Iran but hierarchy and relationships still dominate. Sovereign wealth fund relationships are the unlock. Emiratisation compliance is mandatory."
    },

    // =========================================================================
    // CONFUCIAN ASIA (China, Japan, South Korea, Singapore, Taiwan)
    // =========================================================================
    "Confucian_Asia_SG": {
        label: "Confucian Asia — Singapore",
        globe_cluster: "Confucian_Asia",
        country: "SG",
        hofstede: {
            power_distance: 74,
            individualism: 20,
            masculinity: 48,
            uncertainty_avoidance: 8,
            long_term_orientation: 72,
            indulgence: 46
        },
        cultural_context: "High power distance with meritocratic overlay. Group harmony and face-saving paramount. Long-term orientation drives strategy. Government-linked companies (GLCs) dominate. Kiasu (fear of losing out) culture drives competitiveness. English + Mandarin bilingual business environment.",
        weight_adjustments: {
            strategic_vision: +0.05, integrity: +0.05, cognitive_ability: +0.05,
            resilience: 0, results_orientation: +0.05,
            emotional_intelligence: +0.1, adaptability: +0.05, self_awareness: +0.05,
            learning_agility: +0.05, executive_presence: 0,
            decisiveness: -0.05, energy_drive: 0,
            industry_expertise: 0, functional_excellence: +0.05, financial_acumen: +0.05,
            digital_fluency: +0.05, global_perspective: +0.05, talent_development: +0.05,
            stakeholder_management: +0.1, board_governance: 0,
            crisis_leadership: 0, innovation_leadership: 0, change_management: -0.05,
            customer_centricity: 0, operational_excellence: +0.05
        },
        base_weights: {
            strategic_vision: 10, integrity: 10, cognitive_ability: 9,
            resilience: 8, results_orientation: 9,
            emotional_intelligence: 9, adaptability: 8, self_awareness: 7,
            learning_agility: 8, executive_presence: 8,
            decisiveness: 6, energy_drive: 7,
            industry_expertise: 7, functional_excellence: 7, financial_acumen: 8,
            digital_fluency: 7, global_perspective: 8, talent_development: 7,
            stakeholder_management: 9, board_governance: 7,
            crisis_leadership: 7, innovation_leadership: 7, change_management: 6,
            customer_centricity: 7, operational_excellence: 8
        },
        thresholds: {
            strategic_vision: 7, integrity: 8, cognitive_ability: 7,
            resilience: 6, results_orientation: 7
        },
        additional_criteria: [
            {
                id: "relationship_networks",
                name: "Government & GLC Networks",
                weight: 8,
                description: "Access to Temasek, GIC, statutory boards. Understanding of government-linked company ecosystem.",
                threshold: 6
            },
            {
                id: "hierarchical_respect",
                name: "Face & Harmony Management",
                weight: 8,
                description: "Ability to navigate face-saving dynamics. Indirect communication mastery. Never causing public embarrassment to seniors.",
                threshold: 6
            }
        ],
        notes: "Singapore blends Confucian hierarchy with British governance traditions. Meritocracy is real but expressed through group achievement. Government relationships are business prerequisites."
    },

    // =========================================================================
    // GERMANIC EUROPE (Germany, Austria, Switzerland, Netherlands)
    // =========================================================================
    "Germanic_DE": {
        label: "Germanic Europe — Germany",
        globe_cluster: "Germanic_Europe",
        country: "DE",
        hofstede: {
            power_distance: 35,
            individualism: 67,
            masculinity: 66,
            uncertainty_avoidance: 65,
            long_term_orientation: 83,
            indulgence: 40
        },
        cultural_context: "Low power distance, high uncertainty avoidance. Mittelstand culture values technical depth and engineering excellence. Consensus-driven (Mitbestimmung). Long-term planning horizon. Process-oriented. Works council / Betriebsrat co-determination rights.",
        weight_adjustments: {
            strategic_vision: 0, integrity: +0.05, cognitive_ability: +0.1,
            resilience: 0, results_orientation: 0,
            emotional_intelligence: -0.05, adaptability: -0.05, self_awareness: 0,
            learning_agility: 0, executive_presence: -0.05,
            decisiveness: -0.05, energy_drive: -0.05,
            industry_expertise: +0.1, functional_excellence: +0.1, financial_acumen: 0,
            digital_fluency: +0.05, global_perspective: 0, talent_development: +0.05,
            stakeholder_management: +0.05, board_governance: +0.05,
            crisis_leadership: 0, innovation_leadership: +0.05, change_management: -0.05,
            customer_centricity: 0, operational_excellence: +0.1
        },
        base_weights: {
            strategic_vision: 9, integrity: 10, cognitive_ability: 9,
            resilience: 8, results_orientation: 8,
            emotional_intelligence: 6, adaptability: 6, self_awareness: 6,
            learning_agility: 7, executive_presence: 7,
            decisiveness: 6, energy_drive: 6,
            industry_expertise: 9, functional_excellence: 8, financial_acumen: 7,
            digital_fluency: 7, global_perspective: 7, talent_development: 7,
            stakeholder_management: 8, board_governance: 8,
            crisis_leadership: 7, innovation_leadership: 7, change_management: 6,
            customer_centricity: 6, operational_excellence: 9
        },
        thresholds: {
            strategic_vision: 7, integrity: 8, cognitive_ability: 7,
            resilience: 6, results_orientation: 7
        },
        additional_criteria: [
            {
                id: "technical_depth",
                name: "Technical / Engineering Depth",
                weight: 8,
                description: "German executives expected to have deep Fachkompetenz (subject matter expertise). Pure 'generalist' leaders viewed with suspicion.",
                threshold: 6
            },
            {
                id: "consensus_building",
                name: "Mitbestimmung / Co-Determination",
                weight: 7,
                description: "Works council collaboration, supervisory board experience, stakeholder capitalism (not shareholder primacy).",
                threshold: 5
            }
        ],
        notes: "German executive culture prizes technical competence and process rigor over charisma. Engineering excellence is the credential. Co-determination means works councils have real power."
    },

    // =========================================================================
    // LATIN AMERICA (Brazil, Mexico, Colombia, Argentina)
    // =========================================================================
    "Latin_America_BR": {
        label: "Latin America — Brazil",
        globe_cluster: "Latin_America",
        country: "BR",
        hofstede: {
            power_distance: 69,
            individualism: 38,
            masculinity: 49,
            uncertainty_avoidance: 76,
            long_term_orientation: 44,
            indulgence: 59
        },
        cultural_context: "High power distance, group-oriented. Jeitinho brasileiro (creative problem-solving around obstacles). Personal relationships (personalismo) drive business. Bureaucratic navigation essential. Family business culture strong even in multinationals.",
        weight_adjustments: {
            strategic_vision: 0, integrity: +0.05, cognitive_ability: 0,
            resilience: +0.1, results_orientation: -0.05,
            emotional_intelligence: +0.15, adaptability: +0.1, self_awareness: 0,
            learning_agility: 0, executive_presence: +0.05,
            decisiveness: -0.05, energy_drive: +0.05,
            industry_expertise: 0, functional_excellence: 0, financial_acumen: +0.05,
            digital_fluency: 0, global_perspective: 0, talent_development: 0,
            stakeholder_management: +0.1, board_governance: -0.05,
            crisis_leadership: +0.1, innovation_leadership: 0, change_management: +0.05,
            customer_centricity: +0.05, operational_excellence: -0.05
        },
        base_weights: {
            strategic_vision: 9, integrity: 10, cognitive_ability: 8,
            resilience: 9, results_orientation: 7,
            emotional_intelligence: 9, adaptability: 9, self_awareness: 7,
            learning_agility: 7, executive_presence: 9,
            decisiveness: 6, energy_drive: 7,
            industry_expertise: 7, functional_excellence: 6, financial_acumen: 8,
            digital_fluency: 6, global_perspective: 7, talent_development: 7,
            stakeholder_management: 9, board_governance: 6,
            crisis_leadership: 8, innovation_leadership: 6, change_management: 7,
            customer_centricity: 7, operational_excellence: 6
        },
        thresholds: {
            strategic_vision: 6, integrity: 8, cognitive_ability: 6,
            resilience: 7, results_orientation: 6
        },
        additional_criteria: [
            {
                id: "relationship_networks",
                name: "Relationship Networks (Personalismo)",
                weight: 9,
                description: "Personal trust relationships with key stakeholders. Business follows personal bonds. Cold outreach fails.",
                threshold: 7
            },
            {
                id: "bureaucratic_navigation",
                name: "Bureaucratic Navigation",
                weight: 7,
                description: "Ability to navigate complex regulatory/tax environment (nota fiscal, CNPJ complexity, labor laws).",
                threshold: 5
            }
        ],
        notes: "Brazil rewards emotional intelligence and relationship depth. The jeitinho — creative navigation of bureaucratic obstacles — is a core competency. Resilience critical due to economic volatility."
    }
};

// =========================================================================
// PROFILE LOOKUP HELPERS
// =========================================================================

/**
 * Get the best matching cultural profile for a country code.
 * Falls back to Anglo_US if no specific profile exists.
 */
function getCulturalProfile(countryCode) {
    const mapping = {
        'US': 'Anglo_US', 'GB': 'Anglo_US', 'AU': 'Anglo_US', 'CA': 'Anglo_US', 'NZ': 'Anglo_US',
        'IR': 'Middle_East_IR', 'AE': 'Middle_East_AE', 'SA': 'Middle_East_AE', 'KW': 'Middle_East_AE', 'QA': 'Middle_East_AE',
        'SG': 'Confucian_Asia_SG', 'CN': 'Confucian_Asia_SG', 'JP': 'Confucian_Asia_SG', 'KR': 'Confucian_Asia_SG', 'TW': 'Confucian_Asia_SG',
        'DE': 'Germanic_DE', 'AT': 'Germanic_DE', 'CH': 'Germanic_DE', 'NL': 'Germanic_DE',
        'BR': 'Latin_America_BR', 'MX': 'Latin_America_BR', 'CO': 'Latin_America_BR', 'AR': 'Latin_America_BR',
    };
    const key = mapping[countryCode?.toUpperCase()] || 'Anglo_US';
    return CULTURAL_PROFILES[key];
}

/**
 * Get all available profile keys for dropdown.
 */
function getAllProfileOptions() {
    return Object.entries(CULTURAL_PROFILES).map(([key, profile]) => ({
        value: key,
        label: profile.label
    }));
}
