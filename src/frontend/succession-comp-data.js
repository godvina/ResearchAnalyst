/**
 * Executive Compensation Intelligence — Data Tables
 * 
 * Lookup tables for compensation benchmarking, cost-of-living adjustments,
 * notice periods, and non-compete enforceability across global markets.
 * 
 * Keys: "{SECTOR}_{COUNTRY}_{SENIORITY}" e.g. "PRIVATE_US_VP"
 * Values in USD (thousands) unless noted. Bonus/equity as percentages or absolute.
 * P25/P50/P75 = 25th, 50th, 75th percentile market data.
 * 
 * Sources: Radford, Mercer, McLagan survey summaries; Glassdoor; Levels.fyi;
 * public proxy filings; regional salary guides (Hays, Robert Half, Michael Page).
 */

// ============================================================================
// COMP_LOOKUP — Primary compensation benchmarks
// ============================================================================
const COMP_LOOKUP = {

    // ========================================================================
    // UNITED STATES (US)
    // ========================================================================
    PRIVATE_US_VP: {
        base: { p25: 280000, p50: 360000, p75: 450000 },
        bonus_pct: { p25: 30, p50: 50, p75: 80 },
        equity: { p25: 300000, p50: 650000, p75: 1200000 },
        benefits: 45000,
        total: { p25: 689000, p50: 1175000, p75: 2005000 }
    },
    PRIVATE_US_C_SUITE: {
        base: { p25: 400000, p50: 550000, p75: 700000 },
        bonus_pct: { p25: 50, p50: 100, p75: 150 },
        equity: { p25: 1000000, p50: 2500000, p75: 5000000 },
        benefits: 65000,
        total: { p25: 1665000, p50: 3665000, p75: 6815000 }
    },
    PRIVATE_US_DIRECTOR: {
        base: { p25: 180000, p50: 230000, p75: 300000 },
        bonus_pct: { p25: 20, p50: 35, p75: 55 },
        equity: { p25: 100000, p50: 250000, p75: 500000 },
        benefits: 38000,
        total: { p25: 354000, p50: 600500, p75: 1003000 }
    },
    GOVERNMENT_US_VP: {
        base: { p25: 160000, p50: 195000, p75: 225000 },
        bonus_pct: { p25: 5, p50: 10, p75: 15 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 55000,
        total: { p25: 223000, p50: 269500, p75: 313750 }
    },
    GOVERNMENT_US_C_SUITE: {
        base: { p25: 195000, p50: 240000, p75: 285000 },
        bonus_pct: { p25: 8, p50: 15, p75: 22 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 65000,
        total: { p25: 275600, p50: 341000, p75: 412700 }
    },
    GOVERNMENT_US_DIRECTOR: {
        base: { p25: 130000, p50: 160000, p75: 190000 },
        bonus_pct: { p25: 3, p50: 8, p75: 12 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 48000,
        total: { p25: 181900, p50: 220800, p75: 260800 }
    },
    MILITARY_US_VP: {
        base: { p25: 145000, p50: 175000, p75: 210000 },
        bonus_pct: { p25: 0, p50: 5, p75: 10 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 70000,
        total: { p25: 215000, p50: 253750, p75: 301000 }
    },
    MILITARY_US_C_SUITE: {
        base: { p25: 180000, p50: 220000, p75: 260000 },
        bonus_pct: { p25: 0, p50: 5, p75: 10 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 85000,
        total: { p25: 265000, p50: 316000, p75: 371000 }
    },
    MILITARY_US_DIRECTOR: {
        base: { p25: 110000, p50: 140000, p75: 170000 },
        bonus_pct: { p25: 0, p50: 3, p75: 8 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 58000,
        total: { p25: 168000, p50: 202200, p75: 241600 }
    },

    // ========================================================================
    // UNITED KINGDOM (GB)
    // ========================================================================
    PRIVATE_GB_VP: {
        base: { p25: 220000, p50: 290000, p75: 370000 },
        bonus_pct: { p25: 25, p50: 45, p75: 70 },
        equity: { p25: 150000, p50: 350000, p75: 700000 },
        benefits: 40000,
        total: { p25: 465000, p50: 810500, p75: 1329000 }
    },
    PRIVATE_GB_C_SUITE: {
        base: { p25: 350000, p50: 480000, p75: 620000 },
        bonus_pct: { p25: 40, p50: 80, p75: 130 },
        equity: { p25: 600000, p50: 1500000, p75: 3500000 },
        benefits: 55000,
        total: { p25: 1145000, p50: 2439000, p75: 4961000 }
    },
    PRIVATE_GB_DIRECTOR: {
        base: { p25: 150000, p50: 195000, p75: 260000 },
        bonus_pct: { p25: 18, p50: 30, p75: 50 },
        equity: { p25: 60000, p50: 150000, p75: 350000 },
        benefits: 32000,
        total: { p25: 269000, p50: 435500, p75: 772000 }
    },
    GOVERNMENT_GB_VP: {
        base: { p25: 130000, p50: 165000, p75: 200000 },
        bonus_pct: { p25: 5, p50: 12, p75: 18 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 42000,
        total: { p25: 178500, p50: 226800, p75: 278000 }
    },
    GOVERNMENT_GB_C_SUITE: {
        base: { p25: 170000, p50: 210000, p75: 260000 },
        bonus_pct: { p25: 8, p50: 15, p75: 25 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 52000,
        total: { p25: 235600, p50: 293500, p75: 377000 }
    },
    GOVERNMENT_GB_DIRECTOR: {
        base: { p25: 100000, p50: 130000, p75: 165000 },
        bonus_pct: { p25: 3, p50: 8, p75: 14 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 36000,
        total: { p25: 139000, p50: 176400, p75: 224100 }
    },
    MILITARY_GB_VP: {
        base: { p25: 120000, p50: 150000, p75: 180000 },
        bonus_pct: { p25: 0, p50: 5, p75: 10 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 55000,
        total: { p25: 175000, p50: 212500, p75: 253000 }
    },
    MILITARY_GB_C_SUITE: {
        base: { p25: 155000, p50: 190000, p75: 230000 },
        bonus_pct: { p25: 0, p50: 5, p75: 10 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 68000,
        total: { p25: 223000, p50: 267500, p75: 321000 }
    },
    MILITARY_GB_DIRECTOR: {
        base: { p25: 90000, p50: 115000, p75: 145000 },
        bonus_pct: { p25: 0, p50: 3, p75: 7 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 45000,
        total: { p25: 135000, p50: 163450, p75: 200150 }
    },

    // ========================================================================
    // IRAN (IR) — Middle East: includes allowances
    // ========================================================================
    PRIVATE_IR_VP: {
        base: { p25: 180000, p50: 260000, p75: 350000 },
        bonus_pct: { p25: 20, p50: 35, p75: 50 },
        equity: { p25: 0, p50: 25000, p75: 80000 },
        benefits: 30000,
        allowances: { hardship: 45000, housing: 65000, schooling: 35000, security: 25000 },
        total: { p25: 416000, p50: 576000, p75: 780000 }
    },
    PRIVATE_IR_C_SUITE: {
        base: { p25: 280000, p50: 380000, p75: 500000 },
        bonus_pct: { p25: 30, p50: 50, p75: 80 },
        equity: { p25: 0, p50: 50000, p75: 150000 },
        benefits: 45000,
        allowances: { hardship: 65000, housing: 90000, schooling: 50000, security: 40000 },
        total: { p25: 589000, p50: 865000, p75: 1275000 }
    },
    PRIVATE_IR_DIRECTOR: {
        base: { p25: 120000, p50: 175000, p75: 240000 },
        bonus_pct: { p25: 15, p50: 25, p75: 40 },
        equity: { p25: 0, p50: 10000, p75: 40000 },
        benefits: 22000,
        allowances: { hardship: 35000, housing: 50000, schooling: 28000, security: 18000 },
        total: { p25: 283000, p50: 398750, p75: 554000 }
    },
    GOVERNMENT_IR_VP: {
        base: { p25: 95000, p50: 130000, p75: 170000 },
        bonus_pct: { p25: 10, p50: 18, p75: 25 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 25000,
        allowances: { hardship: 30000, housing: 45000, schooling: 25000, security: 20000 },
        total: { p25: 224500, p50: 273400, p75: 322500 }
    },
    GOVERNMENT_IR_C_SUITE: {
        base: { p25: 140000, p50: 185000, p75: 240000 },
        bonus_pct: { p25: 12, p50: 22, p75: 35 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 35000,
        allowances: { hardship: 45000, housing: 60000, schooling: 35000, security: 30000 },
        total: { p25: 321800, p50: 430700, p75: 564000 }
    },
    GOVERNMENT_IR_DIRECTOR: {
        base: { p25: 70000, p50: 95000, p75: 125000 },
        bonus_pct: { p25: 8, p50: 14, p75: 20 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 20000,
        allowances: { hardship: 22000, housing: 35000, schooling: 20000, security: 15000 },
        total: { p25: 172600, p50: 220300, p75: 280000 }
    },
    MILITARY_IR_VP: {
        base: { p25: 80000, p50: 110000, p75: 145000 },
        bonus_pct: { p25: 5, p50: 12, p75: 20 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 30000,
        allowances: { hardship: 35000, housing: 40000, schooling: 22000, security: 25000 },
        total: { p25: 196000, p50: 255200, p75: 321000 }
    },
    MILITARY_IR_C_SUITE: {
        base: { p25: 110000, p50: 150000, p75: 195000 },
        bonus_pct: { p25: 8, p50: 15, p75: 25 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 40000,
        allowances: { hardship: 50000, housing: 55000, schooling: 30000, security: 35000 },
        total: { p25: 293800, p50: 382500, p75: 483750 }
    },
    MILITARY_IR_DIRECTOR: {
        base: { p25: 55000, p50: 78000, p75: 105000 },
        bonus_pct: { p25: 3, p50: 8, p75: 15 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 22000,
        allowances: { hardship: 25000, housing: 30000, schooling: 18000, security: 15000 },
        total: { p25: 148650, p50: 194240, p75: 250750 }
    },

    // ========================================================================
    // UNITED ARAB EMIRATES (AE) — Middle East: includes allowances
    // ========================================================================
    PRIVATE_AE_VP: {
        base: { p25: 250000, p50: 330000, p75: 400000 },
        bonus_pct: { p25: 30, p50: 45, p75: 60 },
        equity: { p25: 50000, p50: 150000, p75: 350000 },
        benefits: 35000,
        allowances: { hardship: 15000, housing: 65000, schooling: 40000, security: 10000 },
        total: { p25: 540000, p50: 783500, p75: 1040000 }
    },
    PRIVATE_AE_C_SUITE: {
        base: { p25: 380000, p50: 500000, p75: 650000 },
        bonus_pct: { p25: 40, p50: 70, p75: 100 },
        equity: { p25: 200000, p50: 500000, p75: 1200000 },
        benefits: 50000,
        allowances: { hardship: 20000, housing: 95000, schooling: 55000, security: 15000 },
        total: { p25: 877000, p50: 1565000, p75: 2665000 }
    },
    PRIVATE_AE_DIRECTOR: {
        base: { p25: 160000, p50: 220000, p75: 290000 },
        bonus_pct: { p25: 20, p50: 35, p75: 50 },
        equity: { p25: 20000, p50: 80000, p75: 180000 },
        benefits: 28000,
        allowances: { hardship: 10000, housing: 50000, schooling: 32000, security: 8000 },
        total: { p25: 320000, p50: 497000, p75: 733000 }
    },
    GOVERNMENT_AE_VP: {
        base: { p25: 180000, p50: 240000, p75: 310000 },
        bonus_pct: { p25: 15, p50: 25, p75: 35 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 40000,
        allowances: { hardship: 12000, housing: 55000, schooling: 35000, security: 8000 },
        total: { p25: 322000, p50: 450000, p75: 576500 }
    },
    GOVERNMENT_AE_C_SUITE: {
        base: { p25: 260000, p50: 350000, p75: 450000 },
        bonus_pct: { p25: 20, p50: 35, p75: 50 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 55000,
        allowances: { hardship: 18000, housing: 80000, schooling: 48000, security: 12000 },
        total: { p25: 477000, p50: 685500, p75: 918000 }
    },
    GOVERNMENT_AE_DIRECTOR: {
        base: { p25: 120000, p50: 165000, p75: 215000 },
        bonus_pct: { p25: 10, p50: 18, p75: 28 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 32000,
        allowances: { hardship: 8000, housing: 42000, schooling: 28000, security: 6000 },
        total: { p25: 230000, p50: 310700, p75: 401200 }
    },
    MILITARY_AE_VP: {
        base: { p25: 140000, p50: 185000, p75: 235000 },
        bonus_pct: { p25: 8, p50: 15, p75: 22 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 45000,
        allowances: { hardship: 15000, housing: 50000, schooling: 30000, security: 12000 },
        total: { p25: 261200, p50: 352750, p75: 443700 }
    },

    // ========================================================================
    // SAUDI ARABIA (SA) — Middle East: includes allowances
    // ========================================================================
    PRIVATE_SA_VP: {
        base: { p25: 240000, p50: 310000, p75: 390000 },
        bonus_pct: { p25: 25, p50: 40, p75: 55 },
        equity: { p25: 30000, p50: 100000, p75: 250000 },
        benefits: 35000,
        allowances: { hardship: 20000, housing: 70000, schooling: 42000, security: 12000 },
        total: { p25: 497000, p50: 721000, p75: 993500 }
    },
    PRIVATE_SA_C_SUITE: {
        base: { p25: 350000, p50: 470000, p75: 600000 },
        bonus_pct: { p25: 35, p50: 60, p75: 90 },
        equity: { p25: 100000, p50: 350000, p75: 900000 },
        benefits: 48000,
        allowances: { hardship: 30000, housing: 100000, schooling: 55000, security: 18000 },
        total: { p25: 773500, p50: 1323000, p75: 2261000 }
    },
    PRIVATE_SA_DIRECTOR: {
        base: { p25: 150000, p50: 210000, p75: 275000 },
        bonus_pct: { p25: 18, p50: 30, p75: 45 },
        equity: { p25: 10000, p50: 50000, p75: 130000 },
        benefits: 25000,
        allowances: { hardship: 15000, housing: 52000, schooling: 30000, security: 8000 },
        total: { p25: 297000, p50: 450000, p75: 643750 }
    },

    // ========================================================================
    // QATAR (QA) — Middle East: includes allowances
    // ========================================================================
    PRIVATE_QA_VP: {
        base: { p25: 230000, p50: 300000, p75: 380000 },
        bonus_pct: { p25: 25, p50: 40, p75: 55 },
        equity: { p25: 20000, p50: 80000, p75: 200000 },
        benefits: 32000,
        allowances: { hardship: 18000, housing: 68000, schooling: 40000, security: 10000 },
        total: { p25: 465500, p50: 688000, p75: 959000 }
    },
    PRIVATE_QA_C_SUITE: {
        base: { p25: 340000, p50: 450000, p75: 580000 },
        bonus_pct: { p25: 35, p50: 60, p75: 85 },
        equity: { p25: 80000, p50: 300000, p75: 800000 },
        benefits: 45000,
        allowances: { hardship: 25000, housing: 95000, schooling: 50000, security: 15000 },
        total: { p25: 724000, p50: 1255000, p75: 2078000 }
    },
    PRIVATE_QA_DIRECTOR: {
        base: { p25: 145000, p50: 200000, p75: 265000 },
        bonus_pct: { p25: 16, p50: 28, p75: 42 },
        equity: { p25: 8000, p50: 40000, p75: 110000 },
        benefits: 24000,
        allowances: { hardship: 12000, housing: 48000, schooling: 28000, security: 7000 },
        total: { p25: 280200, p50: 416000, p75: 604300 }
    },

    // ========================================================================
    // KUWAIT (KW) — Middle East: includes allowances
    // ========================================================================
    PRIVATE_KW_VP: {
        base: { p25: 210000, p50: 280000, p75: 350000 },
        bonus_pct: { p25: 22, p50: 35, p75: 50 },
        equity: { p25: 15000, p50: 60000, p75: 150000 },
        benefits: 30000,
        allowances: { hardship: 16000, housing: 58000, schooling: 35000, security: 9000 },
        total: { p25: 420200, p50: 606000, p75: 842000 }
    },
    PRIVATE_KW_C_SUITE: {
        base: { p25: 310000, p50: 420000, p75: 540000 },
        bonus_pct: { p25: 30, p50: 55, p75: 80 },
        equity: { p25: 60000, p50: 250000, p75: 650000 },
        benefits: 42000,
        allowances: { hardship: 22000, housing: 85000, schooling: 45000, security: 12000 },
        total: { p25: 634000, p50: 1085000, p75: 1808000 }
    },
    PRIVATE_KW_DIRECTOR: {
        base: { p25: 130000, p50: 180000, p75: 240000 },
        bonus_pct: { p25: 14, p50: 25, p75: 38 },
        equity: { p25: 5000, p50: 30000, p75: 85000 },
        benefits: 22000,
        allowances: { hardship: 10000, housing: 42000, schooling: 25000, security: 6000 },
        total: { p25: 250200, p50: 374000, p75: 539200 }
    },

    // ========================================================================
    // SINGAPORE (SG)
    // ========================================================================
    PRIVATE_SG_VP: {
        base: { p25: 230000, p50: 310000, p75: 400000 },
        bonus_pct: { p25: 25, p50: 40, p75: 60 },
        equity: { p25: 100000, p50: 280000, p75: 600000 },
        benefits: 32000,
        total: { p25: 419500, p50: 746000, p75: 1272000 }
    },
    PRIVATE_SG_C_SUITE: {
        base: { p25: 370000, p50: 490000, p75: 630000 },
        bonus_pct: { p25: 40, p50: 70, p75: 110 },
        equity: { p25: 400000, p50: 1000000, p75: 2500000 },
        benefits: 48000,
        total: { p25: 966000, p50: 1881000, p75: 3841000 }
    },
    PRIVATE_SG_DIRECTOR: {
        base: { p25: 150000, p50: 200000, p75: 270000 },
        bonus_pct: { p25: 18, p50: 30, p75: 45 },
        equity: { p25: 40000, p50: 120000, p75: 280000 },
        benefits: 26000,
        total: { p25: 243000, p50: 406000, p75: 697500 }
    },
    GOVERNMENT_SG_VP: {
        base: { p25: 180000, p50: 240000, p75: 310000 },
        bonus_pct: { p25: 15, p50: 28, p75: 40 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 38000,
        total: { p25: 245000, p50: 345200, p75: 472000 }
    },
    GOVERNMENT_SG_C_SUITE: {
        base: { p25: 280000, p50: 380000, p75: 500000 },
        bonus_pct: { p25: 20, p50: 40, p75: 60 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 50000,
        total: { p25: 386000, p50: 582000, p75: 850000 }
    },
    GOVERNMENT_SG_DIRECTOR: {
        base: { p25: 120000, p50: 160000, p75: 210000 },
        bonus_pct: { p25: 12, p50: 22, p75: 32 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 30000,
        total: { p25: 164400, p50: 225200, p75: 307200 }
    },
    MILITARY_SG_VP: {
        base: { p25: 130000, p50: 170000, p75: 215000 },
        bonus_pct: { p25: 8, p50: 15, p75: 22 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 42000,
        total: { p25: 182400, p50: 237500, p75: 304300 }
    },
    MILITARY_SG_C_SUITE: {
        base: { p25: 170000, p50: 220000, p75: 280000 },
        bonus_pct: { p25: 10, p50: 20, p75: 30 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 55000,
        total: { p25: 242000, p50: 319000, p75: 419000 }
    },
    MILITARY_SG_DIRECTOR: {
        base: { p25: 95000, p50: 125000, p75: 160000 },
        bonus_pct: { p25: 5, p50: 12, p75: 18 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 35000,
        total: { p25: 134750, p50: 175000, p75: 223800 }
    },

    // ========================================================================
    // CHINA (CN)
    // ========================================================================
    PRIVATE_CN_VP: {
        base: { p25: 180000, p50: 260000, p75: 360000 },
        bonus_pct: { p25: 20, p50: 40, p75: 65 },
        equity: { p25: 80000, p50: 250000, p75: 550000 },
        benefits: 28000,
        total: { p25: 324000, p50: 642000, p75: 1172000 }
    },
    PRIVATE_CN_C_SUITE: {
        base: { p25: 300000, p50: 420000, p75: 580000 },
        bonus_pct: { p25: 35, p50: 60, p75: 100 },
        equity: { p25: 300000, p50: 800000, p75: 2000000 },
        benefits: 42000,
        total: { p25: 747000, p50: 1514000, p75: 3202000 }
    },
    PRIVATE_CN_DIRECTOR: {
        base: { p25: 120000, p50: 170000, p75: 240000 },
        bonus_pct: { p25: 15, p50: 28, p75: 45 },
        equity: { p25: 30000, p50: 100000, p75: 250000 },
        benefits: 22000,
        total: { p25: 190000, p50: 339600, p75: 620000 }
    },

    // ========================================================================
    // JAPAN (JP)
    // ========================================================================
    PRIVATE_JP_VP: {
        base: { p25: 200000, p50: 280000, p75: 370000 },
        bonus_pct: { p25: 25, p50: 40, p75: 60 },
        equity: { p25: 50000, p50: 150000, p75: 350000 },
        benefits: 35000,
        total: { p25: 335000, p50: 577000, p75: 977000 }
    },
    PRIVATE_JP_C_SUITE: {
        base: { p25: 320000, p50: 440000, p75: 580000 },
        bonus_pct: { p25: 30, p50: 55, p75: 85 },
        equity: { p25: 200000, p50: 600000, p75: 1500000 },
        benefits: 50000,
        total: { p25: 666000, p50: 1332000, p75: 2623000 }
    },
    PRIVATE_JP_DIRECTOR: {
        base: { p25: 130000, p50: 180000, p75: 250000 },
        bonus_pct: { p25: 18, p50: 30, p75: 45 },
        equity: { p25: 20000, p50: 80000, p75: 200000 },
        benefits: 28000,
        total: { p25: 201400, p50: 342000, p75: 590500 }
    },

    // ========================================================================
    // SOUTH KOREA (KR)
    // ========================================================================
    PRIVATE_KR_VP: {
        base: { p25: 190000, p50: 265000, p75: 350000 },
        bonus_pct: { p25: 22, p50: 38, p75: 55 },
        equity: { p25: 60000, p50: 180000, p75: 400000 },
        benefits: 30000,
        total: { p25: 321800, p50: 575700, p75: 972500 }
    },
    PRIVATE_KR_C_SUITE: {
        base: { p25: 300000, p50: 410000, p75: 550000 },
        bonus_pct: { p25: 30, p50: 55, p75: 85 },
        equity: { p25: 200000, p50: 550000, p75: 1300000 },
        benefits: 45000,
        total: { p25: 635000, p50: 1230500, p75: 2362500 }
    },
    PRIVATE_KR_DIRECTOR: {
        base: { p25: 125000, p50: 175000, p75: 235000 },
        bonus_pct: { p25: 16, p50: 28, p75: 42 },
        equity: { p25: 25000, p50: 80000, p75: 180000 },
        benefits: 24000,
        total: { p25: 194000, p50: 328000, p75: 542700 }
    },

    // ========================================================================
    // GERMANY (DE) — Values in USD (converted from EUR at ~1.08)
    // ========================================================================
    PRIVATE_DE_VP: {
        base: { p25: 215000, p50: 285000, p75: 375000 },
        bonus_pct: { p25: 20, p50: 35, p75: 50 },
        equity: { p25: 50000, p50: 150000, p75: 350000 },
        benefits: 38000,
        total: { p25: 346000, p50: 572750, p75: 950500 }
    },
    PRIVATE_DE_C_SUITE: {
        base: { p25: 340000, p50: 460000, p75: 600000 },
        bonus_pct: { p25: 30, p50: 55, p75: 80 },
        equity: { p25: 200000, p50: 550000, p75: 1400000 },
        benefits: 52000,
        total: { p25: 694000, p50: 1315000, p75: 2532000 }
    },
    PRIVATE_DE_DIRECTOR: {
        base: { p25: 140000, p50: 190000, p75: 260000 },
        bonus_pct: { p25: 15, p50: 25, p75: 38 },
        equity: { p25: 20000, p50: 70000, p75: 180000 },
        benefits: 32000,
        total: { p25: 213000, p50: 339500, p75: 570800 }
    },
    GOVERNMENT_DE_VP: {
        base: { p25: 130000, p50: 170000, p75: 210000 },
        bonus_pct: { p25: 5, p50: 10, p75: 18 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 45000,
        total: { p25: 181500, p50: 232000, p75: 292800 }
    },
    GOVERNMENT_DE_C_SUITE: {
        base: { p25: 180000, p50: 230000, p75: 290000 },
        bonus_pct: { p25: 8, p50: 15, p75: 25 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 55000,
        total: { p25: 249400, p50: 319500, p75: 417500 }
    },
    GOVERNMENT_DE_DIRECTOR: {
        base: { p25: 95000, p50: 125000, p75: 160000 },
        bonus_pct: { p25: 3, p50: 8, p75: 14 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 38000,
        total: { p25: 135850, p50: 173000, p75: 220400 }
    },
    MILITARY_DE_VP: {
        base: { p25: 110000, p50: 145000, p75: 185000 },
        bonus_pct: { p25: 0, p50: 5, p75: 10 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 50000,
        total: { p25: 160000, p50: 202250, p75: 253500 }
    },
    MILITARY_DE_C_SUITE: {
        base: { p25: 145000, p50: 185000, p75: 230000 },
        bonus_pct: { p25: 0, p50: 5, p75: 12 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 62000,
        total: { p25: 207000, p50: 256250, p75: 319600 }
    },
    MILITARY_DE_DIRECTOR: {
        base: { p25: 82000, p50: 108000, p75: 140000 },
        bonus_pct: { p25: 0, p50: 3, p75: 8 },
        equity: { p25: 0, p50: 0, p75: 0 },
        benefits: 42000,
        total: { p25: 124000, p50: 153240, p75: 193200 }
    },

    // ========================================================================
    // AUSTRIA (AT)
    // ========================================================================
    PRIVATE_AT_VP: {
        base: { p25: 195000, p50: 260000, p75: 340000 },
        bonus_pct: { p25: 18, p50: 30, p75: 45 },
        equity: { p25: 30000, p50: 100000, p75: 250000 },
        benefits: 35000,
        total: { p25: 295100, p50: 473000, p75: 778000 }
    },
    PRIVATE_AT_C_SUITE: {
        base: { p25: 300000, p50: 410000, p75: 540000 },
        bonus_pct: { p25: 25, p50: 45, p75: 70 },
        equity: { p25: 120000, p50: 380000, p75: 1000000 },
        benefits: 48000,
        total: { p25: 543000, p50: 1022500, p75: 1966000 }
    },
    PRIVATE_AT_DIRECTOR: {
        base: { p25: 130000, p50: 175000, p75: 235000 },
        bonus_pct: { p25: 14, p50: 22, p75: 35 },
        equity: { p25: 15000, p50: 50000, p75: 140000 },
        benefits: 30000,
        total: { p25: 193200, p50: 293500, p75: 487250 }
    },

    // ========================================================================
    // SWITZERLAND (CH)
    // ========================================================================
    PRIVATE_CH_VP: {
        base: { p25: 260000, p50: 350000, p75: 450000 },
        bonus_pct: { p25: 25, p50: 40, p75: 60 },
        equity: { p25: 80000, p50: 220000, p75: 500000 },
        benefits: 42000,
        total: { p25: 447000, p50: 752000, p75: 1262000 }
    },
    PRIVATE_CH_C_SUITE: {
        base: { p25: 420000, p50: 560000, p75: 720000 },
        bonus_pct: { p25: 40, p50: 70, p75: 110 },
        equity: { p25: 400000, p50: 1100000, p75: 2800000 },
        benefits: 60000,
        total: { p25: 1048000, p50: 2112000, p75: 4372000 }
    },
    PRIVATE_CH_DIRECTOR: {
        base: { p25: 170000, p50: 230000, p75: 310000 },
        bonus_pct: { p25: 18, p50: 30, p75: 45 },
        equity: { p25: 40000, p50: 120000, p75: 280000 },
        benefits: 35000,
        total: { p25: 275600, p50: 454000, p75: 764500 }
    },

    // ========================================================================
    // NETHERLANDS (NL)
    // ========================================================================
    PRIVATE_NL_VP: {
        base: { p25: 200000, p50: 270000, p75: 350000 },
        bonus_pct: { p25: 20, p50: 35, p75: 50 },
        equity: { p25: 40000, p50: 130000, p75: 320000 },
        benefits: 36000,
        total: { p25: 316000, p50: 530500, p75: 881000 }
    },
    PRIVATE_NL_C_SUITE: {
        base: { p25: 320000, p50: 430000, p75: 570000 },
        bonus_pct: { p25: 30, p50: 50, p75: 80 },
        equity: { p25: 200000, p50: 550000, p75: 1400000 },
        benefits: 50000,
        total: { p25: 666000, p50: 1245000, p75: 2476000 }
    },
    PRIVATE_NL_DIRECTOR: {
        base: { p25: 135000, p50: 185000, p75: 250000 },
        bonus_pct: { p25: 15, p50: 25, p75: 38 },
        equity: { p25: 20000, p50: 70000, p75: 180000 },
        benefits: 30000,
        total: { p25: 205250, p50: 331250, p75: 555000 }
    },

    // ========================================================================
    // BRAZIL (BR)
    // ========================================================================
    PRIVATE_BR_VP: {
        base: { p25: 150000, p50: 210000, p75: 290000 },
        bonus_pct: { p25: 20, p50: 35, p75: 55 },
        equity: { p25: 40000, p50: 120000, p75: 300000 },
        benefits: 25000,
        total: { p25: 245000, p50: 428500, p75: 774500 }
    },
    PRIVATE_BR_C_SUITE: {
        base: { p25: 250000, p50: 360000, p75: 480000 },
        bonus_pct: { p25: 30, p50: 55, p75: 85 },
        equity: { p25: 150000, p50: 450000, p75: 1100000 },
        benefits: 38000,
        total: { p25: 513000, p50: 1046000, p75: 1946000 }
    },
    PRIVATE_BR_DIRECTOR: {
        base: { p25: 100000, p50: 145000, p75: 200000 },
        bonus_pct: { p25: 15, p50: 25, p75: 40 },
        equity: { p25: 15000, p50: 50000, p75: 140000 },
        benefits: 20000,
        total: { p25: 150000, p50: 251250, p75: 440000 }
    },

    // ========================================================================
    // MEXICO (MX)
    // ========================================================================
    PRIVATE_MX_VP: {
        base: { p25: 140000, p50: 195000, p75: 270000 },
        bonus_pct: { p25: 18, p50: 30, p75: 48 },
        equity: { p25: 30000, p50: 100000, p75: 250000 },
        benefits: 22000,
        total: { p25: 217200, p50: 375500, p75: 671600 }
    },
    PRIVATE_MX_C_SUITE: {
        base: { p25: 230000, p50: 330000, p75: 440000 },
        bonus_pct: { p25: 25, p50: 50, p75: 80 },
        equity: { p25: 100000, p50: 350000, p75: 900000 },
        benefits: 35000,
        total: { p25: 422500, p50: 880000, p75: 1727000 }
    },
    PRIVATE_MX_DIRECTOR: {
        base: { p25: 90000, p50: 130000, p75: 180000 },
        bonus_pct: { p25: 12, p50: 22, p75: 35 },
        equity: { p25: 10000, p50: 40000, p75: 110000 },
        benefits: 18000,
        total: { p25: 128800, p50: 216600, p75: 371000 }
    },

    // ========================================================================
    // FRANCE (FR)
    // ========================================================================
    PRIVATE_FR_VP: {
        base: { p25: 200000, p50: 270000, p75: 350000 },
        bonus_pct: { p25: 18, p50: 32, p75: 48 },
        equity: { p25: 40000, p50: 130000, p75: 320000 },
        benefits: 38000,
        total: { p25: 314000, p50: 524400, p75: 876000 }
    },
    PRIVATE_FR_C_SUITE: {
        base: { p25: 320000, p50: 440000, p75: 580000 },
        bonus_pct: { p25: 28, p50: 50, p75: 80 },
        equity: { p25: 180000, p50: 500000, p75: 1300000 },
        benefits: 50000,
        total: { p25: 639600, p50: 1210000, p75: 2394000 }
    },
    PRIVATE_FR_DIRECTOR: {
        base: { p25: 130000, p50: 180000, p75: 240000 },
        bonus_pct: { p25: 14, p50: 24, p75: 36 },
        equity: { p25: 18000, p50: 60000, p75: 160000 },
        benefits: 32000,
        total: { p25: 198200, p50: 315200, p75: 518400 }
    },

    // ========================================================================
    // INDIA (IN)
    // ========================================================================
    PRIVATE_IN_VP: {
        base: { p25: 120000, p50: 175000, p75: 250000 },
        bonus_pct: { p25: 18, p50: 30, p75: 50 },
        equity: { p25: 50000, p50: 150000, p75: 380000 },
        benefits: 20000,
        total: { p25: 211600, p50: 397500, p75: 775000 }
    },
    PRIVATE_IN_C_SUITE: {
        base: { p25: 200000, p50: 300000, p75: 420000 },
        bonus_pct: { p25: 25, p50: 50, p75: 80 },
        equity: { p25: 150000, p50: 500000, p75: 1200000 },
        benefits: 32000,
        total: { p25: 432000, p50: 982000, p75: 1988000 }
    },
    PRIVATE_IN_DIRECTOR: {
        base: { p25: 80000, p50: 120000, p75: 175000 },
        bonus_pct: { p25: 14, p50: 24, p75: 38 },
        equity: { p25: 20000, p50: 65000, p75: 180000 },
        benefits: 15000,
        total: { p25: 126200, p50: 228800, p75: 436500 }
    },

    // ========================================================================
    // AUSTRALIA (AU)
    // ========================================================================
    PRIVATE_AU_VP: {
        base: { p25: 220000, p50: 300000, p75: 390000 },
        bonus_pct: { p25: 22, p50: 38, p75: 55 },
        equity: { p25: 80000, p50: 220000, p75: 480000 },
        benefits: 35000,
        total: { p25: 383400, p50: 669000, p75: 1119500 }
    },
    PRIVATE_AU_C_SUITE: {
        base: { p25: 350000, p50: 470000, p75: 620000 },
        bonus_pct: { p25: 35, p50: 60, p75: 90 },
        equity: { p25: 250000, p50: 700000, p75: 1800000 },
        benefits: 50000,
        total: { p25: 772500, p50: 1502000, p75: 3028000 }
    },
    PRIVATE_AU_DIRECTOR: {
        base: { p25: 145000, p50: 200000, p75: 270000 },
        bonus_pct: { p25: 16, p50: 28, p75: 42 },
        equity: { p25: 30000, p50: 100000, p75: 240000 },
        benefits: 28000,
        total: { p25: 226200, p50: 384000, p75: 651400 }
    },

    // ========================================================================
    // CANADA (CA)
    // ========================================================================
    PRIVATE_CA_VP: {
        base: { p25: 230000, p50: 310000, p75: 400000 },
        bonus_pct: { p25: 25, p50: 42, p75: 60 },
        equity: { p25: 100000, p50: 280000, p75: 600000 },
        benefits: 38000,
        total: { p25: 425500, p50: 758200, p75: 1278000 }
    },
    PRIVATE_CA_C_SUITE: {
        base: { p25: 360000, p50: 490000, p75: 640000 },
        bonus_pct: { p25: 40, p50: 70, p75: 110 },
        equity: { p25: 350000, p50: 900000, p75: 2200000 },
        benefits: 52000,
        total: { p25: 906000, p50: 1785000, p75: 3596000 }
    },
    PRIVATE_CA_DIRECTOR: {
        base: { p25: 150000, p50: 205000, p75: 275000 },
        bonus_pct: { p25: 18, p50: 30, p75: 45 },
        equity: { p25: 50000, p50: 140000, p75: 320000 },
        benefits: 32000,
        total: { p25: 259000, p50: 438500, p75: 750750 }
    },

    // ========================================================================
    // NEW ZEALAND (NZ)
    // ========================================================================
    PRIVATE_NZ_VP: {
        base: { p25: 180000, p50: 245000, p75: 320000 },
        bonus_pct: { p25: 18, p50: 30, p75: 45 },
        equity: { p25: 40000, p50: 120000, p75: 280000 },
        benefits: 30000,
        total: { p25: 282400, p50: 468500, p75: 774000 }
    },
    PRIVATE_NZ_C_SUITE: {
        base: { p25: 290000, p50: 390000, p75: 510000 },
        bonus_pct: { p25: 28, p50: 48, p75: 75 },
        equity: { p25: 150000, p50: 450000, p75: 1100000 },
        benefits: 42000,
        total: { p25: 563200, p50: 1069200, p75: 2034500 }
    },
    PRIVATE_NZ_DIRECTOR: {
        base: { p25: 120000, p50: 165000, p75: 225000 },
        bonus_pct: { p25: 14, p50: 24, p75: 36 },
        equity: { p25: 20000, p50: 60000, p75: 150000 },
        benefits: 25000,
        total: { p25: 181800, p50: 289600, p75: 481000 }
    }
};


// ============================================================================
// COST_OF_LIVING_INDEX — Multiplier relative to US = 1.00
// Sources: Mercer Cost of Living Survey, Numbeo, ECA International
// ============================================================================
const COST_OF_LIVING_INDEX = {
    US: 1.00,
    GB: 0.95,
    IR: 0.45,
    AE: 0.88,
    SA: 0.72,
    QA: 0.82,
    KW: 0.70,
    SG: 1.05,
    CN: 0.55,
    JP: 0.85,
    KR: 0.78,
    DE: 0.82,
    AT: 0.80,
    CH: 1.30,
    NL: 0.84,
    BR: 0.48,
    MX: 0.42,
    FR: 0.86,
    IN: 0.32,
    AU: 0.92,
    CA: 0.88,
    NZ: 0.82
};


// ============================================================================
// NOTICE_PERIODS — Months required by country and seniority
// Based on statutory minimums + typical contractual terms for executives
// ============================================================================
const NOTICE_PERIODS = {
    US: { VP: 0, C_SUITE: 0, DIRECTOR: 0 },        // At-will; contractual garden leave common
    GB: { VP: 6, C_SUITE: 12, DIRECTOR: 3 },
    IR: { VP: 3, C_SUITE: 6, DIRECTOR: 2 },
    AE: { VP: 3, C_SUITE: 6, DIRECTOR: 2 },
    SA: { VP: 3, C_SUITE: 6, DIRECTOR: 2 },
    QA: { VP: 3, C_SUITE: 6, DIRECTOR: 2 },
    KW: { VP: 3, C_SUITE: 6, DIRECTOR: 2 },
    SG: { VP: 3, C_SUITE: 6, DIRECTOR: 2 },
    CN: { VP: 1, C_SUITE: 3, DIRECTOR: 1 },
    JP: { VP: 3, C_SUITE: 6, DIRECTOR: 2 },
    KR: { VP: 2, C_SUITE: 3, DIRECTOR: 1 },
    DE: { VP: 6, C_SUITE: 12, DIRECTOR: 3 },
    AT: { VP: 5, C_SUITE: 12, DIRECTOR: 3 },
    CH: { VP: 6, C_SUITE: 12, DIRECTOR: 3 },
    NL: { VP: 4, C_SUITE: 6, DIRECTOR: 2 },
    BR: { VP: 1, C_SUITE: 3, DIRECTOR: 1 },
    MX: { VP: 1, C_SUITE: 3, DIRECTOR: 1 },
    FR: { VP: 3, C_SUITE: 6, DIRECTOR: 3 },
    IN: { VP: 3, C_SUITE: 6, DIRECTOR: 2 },
    AU: { VP: 3, C_SUITE: 6, DIRECTOR: 2 },
    CA: { VP: 3, C_SUITE: 6, DIRECTOR: 2 },
    NZ: { VP: 3, C_SUITE: 6, DIRECTOR: 2 }
};


// ============================================================================
// NON_COMPETE_ENFORCEABILITY
// Values: "enforceable" | "unenforceable" | "limited"
// Key format: country code, or "country_state" for US states with distinct rules
// ============================================================================
const NON_COMPETE_ENFORCEABILITY = {
    // US — state-by-state variation
    US: "limited",                    // Federal: FTC rule pending; varies by state
    US_CA: "unenforceable",           // California: categorically void
    US_CO: "limited",                 // Colorado: only for highly-compensated + management
    US_NY: "limited",                 // New York: narrowly enforced, pending ban
    US_TX: "enforceable",             // Texas: enforceable if reasonable scope
    US_FL: "enforceable",             // Florida: strong enforcement
    US_IL: "limited",                 // Illinois: banned under $75K threshold
    US_MA: "limited",                 // Massachusetts: 12-month max, garden leave required
    US_WA: "limited",                 // Washington: banned under $116K threshold
    US_MN: "unenforceable",           // Minnesota: banned as of 2023
    US_OK: "unenforceable",           // Oklahoma: generally void
    US_ND: "unenforceable",           // North Dakota: generally void

    // International
    GB: "enforceable",                // UK: enforceable if reasonable (6-12 months typical)
    IR: "limited",                    // Iran: limited enforcement, courts skeptical
    AE: "enforceable",               // UAE: enforceable (max 2 years per labor law)
    SA: "enforceable",               // Saudi: enforceable (max 2 years)
    QA: "enforceable",               // Qatar: enforceable (max 2 years)
    KW: "enforceable",               // Kuwait: enforceable if reasonable
    SG: "enforceable",               // Singapore: enforceable if reasonable
    CN: "enforceable",               // China: enforceable (max 2 years, compensation required)
    JP: "limited",                    // Japan: enforceable only if compensation provided
    KR: "limited",                    // South Korea: limited — courts require compensation
    DE: "enforceable",               // Germany: enforceable (max 2 years, 50% salary required)
    AT: "enforceable",               // Austria: enforceable (max 1 year)
    CH: "enforceable",               // Switzerland: enforceable (max 3 years)
    NL: "enforceable",               // Netherlands: enforceable if reasonable
    BR: "limited",                    // Brazil: limited enforcement, no clear statute
    MX: "unenforceable",             // Mexico: generally not enforceable
    FR: "enforceable",               // France: enforceable (compensation required, 33%+ salary)
    IN: "limited",                    // India: generally unenforceable (Section 27 Indian Contract Act)
    AU: "limited",                    // Australia: enforceable if reasonable, courts skeptical
    CA: "limited",                    // Canada: enforceable if reasonable, varies by province
    NZ: "limited"                     // New Zealand: enforceable only if reasonable and compensated
};
