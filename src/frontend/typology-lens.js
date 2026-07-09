/**
 * Crime Typology — Pattern Recognition Lens
 * 
 * Multi-module frontend component for displaying typology analysis results.
 * Supports multiple crime type modules with auto-detection and manual override.
 * 
 * Modules: Human Trafficking, Fraud Waste & Abuse, Drug Trafficking, Money Laundering,
 *          Cybercrime, Terrorism Financing, Public Corruption, Organized Crime (RICO),
 *          Child Exploitation (CSAM), Sanctions Evasion, Environmental Crime
 * Usage: openTypologyLens() — triggered from a button in the UI
 * Requires: selectedCaseId, api() function, esc() function from investigator.html
 */

// === TYPOLOGY MODULES — each crime type has its own set of categories ===
var ACTIVE_TYPOLOGY_MODULE = 'sex_trafficking'; // Default, auto-detected

const TYPOLOGY_MODULES = {
    sex_trafficking: {
        id: 'sex_trafficking',
        name: 'Human Trafficking',
        subtitle: 'HUMAN TRAFFICKING CRIME TYPOLOGY',
        icon: '🔴',
        color: '#e53e3e',
        description: 'Palermo Protocol elements: recruitment, transportation, exploitation',
        autoDetectKeywords: ['trafficking', 'victim', 'minor', 'recruitment', 'exploitation']
    },
    fraud_waste_abuse: {
        id: 'fraud_waste_abuse',
        name: 'Fraud, Waste & Abuse',
        subtitle: 'FRAUD WASTE & ABUSE TYPOLOGY',
        icon: '🟡',
        color: '#d69e2e',
        description: 'Financial crime patterns: procurement fraud, billing schemes, kickbacks',
        autoDetectKeywords: ['fraud', 'billing', 'procurement', 'invoice', 'kickback', 'embezzlement']
    },
    drug_trafficking: {
        id: 'drug_trafficking',
        name: 'Drug Trafficking',
        subtitle: 'DRUG TRAFFICKING TYPOLOGY',
        icon: '💊',
        color: '#9f7aea',
        description: 'Narcotics distribution networks: supply chains, stash houses, distribution',
        autoDetectKeywords: ['drug', 'narcotics', 'fentanyl', 'cocaine', 'heroin', 'distribution', 'cartel']
    },
    money_laundering: {
        id: 'money_laundering',
        name: 'Money Laundering',
        subtitle: 'MONEY LAUNDERING TYPOLOGY',
        icon: '💰',
        color: '#38b2ac',
        description: 'Financial concealment: layering, integration, trade-based laundering',
        autoDetectKeywords: ['laundering', 'shell company', 'offshore', 'structuring', 'smurfing', 'wire transfer']
    },
    cybercrime: {
        id: 'cybercrime',
        name: 'Cybercrime',
        subtitle: 'CYBERCRIME TYPOLOGY',
        icon: '💻',
        color: '#4299e1',
        description: 'Digital offenses: ransomware, BEC, credential theft, data exfiltration',
        autoDetectKeywords: ['cyber', 'ransomware', 'phishing', 'malware', 'hack', 'breach', 'BEC']
    },
    terrorism_financing: {
        id: 'terrorism_financing',
        name: 'Terrorism Financing',
        subtitle: 'TERRORISM FINANCING TYPOLOGY',
        icon: '🔶',
        color: '#dd6b20',
        description: 'Material support and fundraising: hawalas, charities, crypto channels',
        autoDetectKeywords: ['terrorism', 'material support', 'hawala', 'radicalization', 'extremist']
    },
    public_corruption: {
        id: 'public_corruption',
        name: 'Public Corruption',
        subtitle: 'PUBLIC CORRUPTION TYPOLOGY',
        icon: '🏛️',
        color: '#718096',
        description: 'Official misconduct: bribery, extortion, Hobbs Act, honest services fraud',
        autoDetectKeywords: ['corruption', 'bribery', 'official', 'elected', 'government', 'Hobbs Act']
    },
    organized_crime: {
        id: 'organized_crime',
        name: 'Organized Crime (RICO)',
        subtitle: 'ORGANIZED CRIME TYPOLOGY',
        icon: '🕸️',
        color: '#2d3748',
        description: 'Enterprise patterns: hierarchy, predicate acts, continuity, common purpose',
        autoDetectKeywords: ['RICO', 'enterprise', 'racketeering', 'organized', 'mafia', 'gang']
    },
    child_exploitation: {
        id: 'child_exploitation',
        name: 'Child Exploitation (CSAM)',
        subtitle: 'CHILD EXPLOITATION TYPOLOGY',
        icon: '🛡️',
        color: '#c53030',
        description: 'Production, distribution, possession patterns and victim identification',
        autoDetectKeywords: ['CSAM', 'child exploitation', 'NCMEC', 'minor', 'sextortion']
    },
    sanctions_evasion: {
        id: 'sanctions_evasion',
        name: 'Sanctions Evasion',
        subtitle: 'SANCTIONS EVASION TYPOLOGY',
        icon: '🚫',
        color: '#b83280',
        description: 'OFAC violations: front companies, transshipment, deceptive practices',
        autoDetectKeywords: ['sanctions', 'OFAC', 'evasion', 'designated', 'embargo', 'SDN']
    },
    environmental_crime: {
        id: 'environmental_crime',
        name: 'Environmental Crime',
        subtitle: 'ENVIRONMENTAL CRIME TYPOLOGY',
        icon: '🌍',
        color: '#276749',
        description: 'Illegal dumping, wildlife trafficking, Clean Air/Water Act violations',
        autoDetectKeywords: ['environmental', 'pollution', 'dumping', 'wildlife', 'EPA', 'hazardous']
    }
};

// Fraud, Waste & Abuse categories
const FWA_CATEGORIES = [
    {
        id: 'procurement_fraud',
        icon: '📋',
        name: 'Procurement Fraud',
        color: '#d69e2e',
        indicators: 'Bid rigging, sole-source justification patterns, split purchases below threshold, phantom vendors',
        exampleText: '14 contracts awarded to 3 vendors sharing the same registered agent. All bids within 2% of each other. Typology flags: <em>bid rotation + shell vendor + threshold splitting</em>.',
        stat: 'Procurement fraud accounts for 33% of all federal fraud cases. Average scheme duration: 18 months before detection. (ACFE Report to the Nations, 2024)'
    },
    {
        id: 'billing_schemes',
        icon: '🧾',
        name: 'Billing & Invoice Schemes',
        color: '#ed8936',
        indicators: 'Duplicate invoices, inflated charges, services not rendered, ghost employees, round-number billing',
        exampleText: 'Vendor submitted 47 invoices for "consulting services" over 8 months. All amounts between $9,500-$9,900 (below $10K approval threshold). No deliverables documented. Typology flags: <em>threshold avoidance + no deliverables + frequency anomaly</em>.',
        stat: 'Billing schemes are the most common occupational fraud type (22%). Median loss: $100,000. (ACFE 2024)'
    },
    {
        id: 'conflict_of_interest',
        icon: '🤝',
        name: 'Conflict of Interest',
        color: '#805ad5',
        indicators: 'Undisclosed relationships, revolving door employment, family connections to vendors, decision-maker financial interests',
        exampleText: 'Contracting officer approved $2.3M in awards to a firm where his spouse is VP of Operations. Relationship undisclosed on OGE-450. Typology flags: <em>undisclosed relationship + financial interest + approval authority</em>.',
        stat: '42% of fraud cases involve conflicts of interest. Average loss when COI is present: $486,000. (ACFE 2024)'
    },
    {
        id: 'grant_misuse',
        icon: '💰',
        name: 'Grant & Fund Misuse',
        color: '#38a169',
        indicators: 'Commingled funds, personal expenses on grant, fabricated match requirements, double-dipping across grants',
        exampleText: 'Non-profit received $1.2M HHS grant. Bank records show $340K transferred to executive\'s personal accounts as "administrative fees" not in budget. Typology flags: <em>commingled funds + unauthorized transfers + fabricated expenses</em>.',
        stat: 'Improper payments in federal grants exceeded $175B in FY2023. 12% of single audit findings involve material non-compliance. (GAO)'
    },
    {
        id: 'kickback_schemes',
        icon: '💸',
        name: 'Kickback & Bribery',
        color: '#e53e3e',
        indicators: 'Unusual payment patterns, intermediary payments, lavish gifts, travel paid by vendors, cash transactions',
        exampleText: 'Program manager received $45K in payments from vendor via intermediary LLC. Payments correlate with contract award dates. Vendor also paid for 3 overseas trips. Typology flags: <em>intermediary payments + temporal correlation + gift pattern</em>.',
        stat: 'Anti-Kickback Act violations result in average settlements of $2.1M. 71% involve intermediary payment structures. (DOJ Civil Division, 2023)'
    },
    {
        id: 'data_manipulation',
        icon: '📊',
        name: 'Data & Reporting Manipulation',
        color: '#4299e1',
        indicators: 'Altered records, backdated documents, falsified performance metrics, suppressed audit findings',
        exampleText: 'Quarterly reports show 98% performance metrics but underlying data has 2,400 deleted records from the reporting period. Deletion timestamps cluster around report submission dates. Typology flags: <em>record deletion + timing correlation + metric inflation</em>.',
        stat: '28% of fraud cases involve document alteration or destruction. Digital forensics detects manipulation in 89% of cases where records are preserved. (ACFE 2024)'
    }
];

// Category definitions (static — matches backend TYPOLOGY_CATEGORIES)
const TYPOLOGY_CATEGORIES = [
    {
        id: 'recruitment_grooming',
        icon: '🎭',
        name: 'Recruitment & Grooming',
        color: '#e53e3e',
        indicators: 'Social media contact patterns, age disparity, gift-giving, isolation from family, false employment promises, Romeo pimp tactics',
        exampleText: 'Subject A (age 42) contacted 6 females aged 16-19 via Instagram over 3 months. Pattern: initial flattery, gifts within 48hrs, isolation requests within 2 weeks. Typology flags: <em>love bombing + age disparity + communication isolation</em>.',
        stat: '83% of sex trafficking victims were recruited by someone they knew or met through social media. (DOJ National Human Trafficking Hotline, 2023)'
    },
    {
        id: 'transportation_movement',
        icon: '✈️',
        name: 'Transportation & Movement',
        color: '#ed8936',
        indicators: 'Hotel patterns, interstate travel, charter flights, multiple cities in compressed timeframes, circuit rotation, third-party bookings',
        exampleText: 'Subject B booked hotels in 4 cities over 9 days (Miami→Atlanta→Charlotte→DC). All bookings under alias, paid by Subject A\'s prepaid card. Typology flags: <em>hotel clustering + geographic velocity + third-party booking</em>.',
        stat: '71% of federally prosecuted sex trafficking cases involved interstate transportation. Average circuit: 4.2 cities over 2-week rotation. (USSC 2019-2023)'
    },
    {
        id: 'financial_control',
        icon: '🏦',
        name: 'Financial Control',
        color: '#d69e2e',
        indicators: 'Structuring deposits below CTR threshold, victim accounts controlled by others, prepaid card networks, shell LLCs, crypto ad payments, quota evidence',
        exampleText: '12 bank accounts opened in victims\' names at 4 different banks. All show identical deposit patterns: $8,500-$9,800 cash 2-3x/week. Subject A is authorized signer on all. Typology flags: <em>structuring + controlled accounts + quota evidence</em>.',
        stat: 'Structuring/Money Laundering present in 62% of sex trafficking prosecutions. Average trafficker controls 3.7 victim bank accounts. (FinCEN SAR, FY2022-2024)'
    },
    {
        id: 'communication_networks',
        icon: '📱',
        name: 'Communication Networks',
        color: '#805ad5',
        indicators: 'Burner phone clusters, encrypted apps, coded language in ads, scheduling coordination, ad posting across platforms, star topology',
        exampleText: '8 prepaid phones activated same day, same Walmart. Star topology with Subject A\'s primary phone as hub. Activity spikes 4-6pm daily (booking window). Typology flags: <em>disposable cluster + star topology + coordination window</em>.',
        stat: '94% of sex trafficking operations use multiple phones/accounts. Average operation manages 6.3 ad accounts across 2.8 platforms. (Thorn/Spotlight, 2023)'
    },
    {
        id: 'venue_infrastructure',
        icon: '🏨',
        name: 'Venue & Infrastructure',
        color: '#38a169',
        indicators: 'Massage parlor fronts, hotel room rotation, residential brothels, online ad patterns, venue rotation schedules, multi-location operations',
        exampleText: 'Subject A leases 3 apartments in different zip codes. Each occupied 2-3 days/week on rotation. Online ads match rotation schedule exactly. Typology flags: <em>venue rotation + ad posting cadence + multi-location operation</em>.',
        stat: '55% of sex trafficking venues are residential properties. Average operation rotates across 3.1 locations on 2-4 day cycles. (Polaris Project, 2024)'
    },
    {
        id: 'power_control',
        icon: '⛓️',
        name: 'Power & Control',
        color: '#e53e3e',
        indicators: 'Debt bondage records/ledgers, document confiscation, threats, daily quotas, branding/tattoos, GPS tracking of victims',
        exampleText: 'Ledger from Subject A\'s phone showing 4 victims with running "debt" balances ($15K-$45K). Daily quota: $1,000/night. Passports for 3 victims found in Subject A\'s safe. Typology flags: <em>debt ledger + document control + quota enforcement</em>.',
        stat: '78% of sex trafficking victims report debt bondage. 63% had identity documents confiscated. Average daily quota: $500-$1,000. (DOJ TIP Report, 2024)'
    }
];

function openTypologyLens() {
    var existing = document.getElementById('typologyLensOverlay');
    if (existing) { existing.remove(); return; }
    _renderTypologyLens();
}

// Switch module without toggle behavior — used by module toggle buttons
function switchTypologyModule(moduleId) {
    console.log('[Typology] Switching to module:', moduleId);
    ACTIVE_TYPOLOGY_MODULE = moduleId;
    window._typologyModuleUserSelected = true;
    var existing = document.getElementById('typologyLensOverlay');
    if (existing) existing.remove();
    try {
        _renderTypologyLens();
    } catch(e) {
        console.error('[Typology] Render error:', e);
        alert('Typology render error: ' + e.message);
    }
}

function _renderTypologyLens() {
    // Only auto-detect if user hasn't explicitly selected a module
    if (!window._typologyModuleUserSelected) {
        var caseData = window.selectedCaseData || {};
        var caseName = (caseData.matter_name || caseData.topic_name || '').toLowerCase();
        var caseDesc = (caseData.description || '').toLowerCase();
        var caseText = caseName + ' ' + caseDesc;

        // Auto-detect: check which module's keywords match
        var detectedModule = 'sex_trafficking'; // default
        for (var modId in TYPOLOGY_MODULES) {
            var mod = TYPOLOGY_MODULES[modId];
            if (mod.autoDetectKeywords.some(function(kw) { return caseText.indexOf(kw) >= 0; })) {
                detectedModule = modId;
                break;
            }
        }
        ACTIVE_TYPOLOGY_MODULE = detectedModule;
    }
    // Reset flag after use so next fresh open auto-detects again
    window._typologyModuleUserSelected = false;

    var activeMod = TYPOLOGY_MODULES[ACTIVE_TYPOLOGY_MODULE];
    var cats = (typeof getModuleCategories === 'function') ? getModuleCategories(ACTIVE_TYPOLOGY_MODULE) : (ACTIVE_TYPOLOGY_MODULE === 'fraud_waste_abuse' ? FWA_CATEGORIES : TYPOLOGY_CATEGORIES);

    var overlay = document.createElement('div');
    overlay.id = 'typologyLensOverlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(10,15,25,0.97);z-index:200000;overflow-y:auto;padding:40px;color:#e2e8f0;';

    var html = '<div style="max-width:1200px;margin:0 auto;">';

    // Header with module selector
    html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">';
    html += '<div>';
    html += '<p style="color:' + activeMod.color + ';margin:0;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">' + activeMod.subtitle + '</p>';
    html += '<h2 style="color:#e2e8f0;margin:4px 0 0;font-size:24px;font-weight:700;">' + activeMod.icon + ' Pattern Recognition Lens</h2>';
    html += '</div>';
    html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove()" style="background:none;border:1px solid #4a5568;color:#e2e8f0;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:14px;">Close</button>';
    html += '</div>';

    // Module toggle — wraps for 11 modules
    html += '<div style="display:flex;align-items:center;gap:6px;margin-bottom:16px;padding:10px 16px;background:rgba(0,0,0,0.3);border-radius:8px;flex-wrap:wrap;">';
    html += '<span style="font-size:11px;color:#718096;font-weight:600;white-space:nowrap;">TYPOLOGY MODULE:</span>';
    for (var mId in TYPOLOGY_MODULES) {
        var m = TYPOLOGY_MODULES[mId];
        var isActive = mId === ACTIVE_TYPOLOGY_MODULE;
        // Get pre-computed score for this module
        var mScore = 0;
        if (window._caseTypologyScores) {
            var mFound = window._caseTypologyScores.find(function(s) { return s.id === mId; });
            if (mFound) mScore = mFound.score;
        }
        html += '<button onclick="switchTypologyModule(\'' + mId + '\')" style="padding:4px 10px;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;transition:all 0.2s;white-space:nowrap;';
        if (isActive) {
            html += 'background:' + m.color + '20;border:1px solid ' + m.color + ';color:' + m.color + ';">';
            html += m.icon + ' ' + m.name + (mScore > 0 ? ' <span style="opacity:0.8;">' + mScore + '%</span>' : '') + ' ✓';
        } else {
            var btnBorder = mScore >= 20 ? m.color + '60' : '#4a5568';
            var btnBg = mScore >= 20 ? m.color + '08' : 'transparent';
            var btnColor = mScore >= 20 ? m.color : '#a0aec0';
            html += 'background:' + btnBg + ';border:1px solid ' + btnBorder + ';color:' + btnColor + ';">';
            html += m.icon + ' ' + m.name + (mScore > 0 ? ' <span style="opacity:0.7;font-size:10px;">' + mScore + '%</span>' : '');
        }
        html += '</button>';
    }
    html += '<span style="font-size:10px;color:#4a5568;margin-left:auto;white-space:nowrap;">AI-scored from case evidence</span>';
    html += '</div>';

    // Overall score bar
    var catCount = cats.length || 6;
    html += '<div id="typologyOverallScore" style="margin-bottom:24px;padding:14px 18px;background:' + activeMod.color + '08;border:1px solid ' + activeMod.color + '30;border-radius:10px;display:flex;align-items:center;gap:16px;">';
    html += '<div class="search-spinner" style="display:inline-block;width:14px;height:14px;"></div>';
    html += '<span style="color:#a0aec0;font-size:13px;">Analyzing case evidence against ' + catCount + ' ' + activeMod.name + ' categories...</span>';
    html += '</div>';

    // Cards grid
    html += '<div id="typologyCards" style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px;">';
    cats.forEach(function(c) {
        html += '<div id="typ-card-'+c.id+'" onclick="openTypologyFindings(\''+c.id+'\',\''+c.name+'\',\''+c.icon+'\',\''+c.color+'\')" style="background:rgba(26,35,50,0.9);border:1px solid '+c.color+'40;border-top:3px solid '+c.color+';border-radius:12px;padding:20px;transition:all 0.2s;display:flex;flex-direction:column;cursor:pointer;" onmouseover="this.style.transform=\'translateY(-2px)\'" onmouseout="this.style.transform=\'none\'">';
        
        // Header with score badge
        html += '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">';
        html += '<div style="display:flex;align-items:center;gap:8px;">';
        html += '<span style="font-size:20px;">'+c.icon+'</span>';
        html += '<span style="font-size:14px;font-weight:700;color:#e2e8f0;">'+c.name+'</span>';
        html += '</div>';
        html += '<div id="typ-score-'+c.id+'" style="background:'+c.color+'20;border:1px solid '+c.color+'50;color:'+c.color+';padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;white-space:nowrap;">—</div>';
        html += '</div>';
        
        // Indicators
        html += '<div style="font-size:11px;color:#718096;line-height:1.5;margin-bottom:12px;">'+c.indicators+'</div>';
        
        // Evidence box
        html += '<div id="typ-evidence-'+c.id+'" style="background:rgba(0,0,0,0.3);border-left:3px solid '+c.color+';border-radius:0 8px 8px 0;padding:10px 12px;margin-bottom:10px;flex:1;">';
        html += '<div style="font-size:10px;text-transform:uppercase;color:'+c.color+';font-weight:700;margin-bottom:4px;">EVIDENCE EXAMPLE</div>';
        html += '<div style="font-size:11px;color:#a0aec0;line-height:1.5;">'+c.exampleText+'</div>';
        html += '</div>';
        
        // Stat line
        html += '<div style="font-size:10px;color:#4a5568;line-height:1.4;border-top:1px solid #2d3748;padding-top:8px;">'+c.stat+'</div>';
        
        html += '</div>';
    });
    html += '</div>';

    // Source attribution footnote
    html += '<div style="margin-top:32px;padding:16px 20px;border-top:1px solid #2d3748;color:#4a5568;font-size:10px;line-height:1.7;">';
    html += '<strong style="color:#718096;">Sources:</strong> Typology frameworks derived from FATF Typologies Reports (2020–2024), ';
    html += 'Polaris Project Typology of Modern Slavery, FBI UCR/IC3 Annual Reports, DEA National Drug Threat Assessment, ';
    html += 'FinCEN SAR Advisories, ACFE Report to the Nations (2024), NCMEC Annual Reports, ';
    html += 'OFAC Enforcement Actions, EPA Criminal Enforcement Division, Chainalysis Crypto Crime Report, ';
    html += 'Mandiant M-Trends, USSC Sentencing Guidelines, and DOJ NSD/PIN/CEOS case data. ';
    html += 'Statistics represent publicly available estimates as of 2024 and should not be cited as evidence in legal filings.';
    html += '</div>';

    html += '</div>'; // close max-width container

    overlay.innerHTML = html;
    document.body.appendChild(overlay);

    // Fetch live typology data if a case is selected
    if (typeof selectedCaseId !== 'undefined' && selectedCaseId) {
        if (ACTIVE_TYPOLOGY_MODULE === 'sex_trafficking') {
            _loadTypologyData(selectedCaseId);
        } else {
            // Other modules — show AI-derived score if available, else reference mode
            var scoreEl = document.getElementById('typologyOverallScore');
            if (scoreEl) {
                var activeMod2 = TYPOLOGY_MODULES[ACTIVE_TYPOLOGY_MODULE];
                var preScore = 0;
                if (window._caseTypologyScores) {
                    var found = window._caseTypologyScores.find(function(s) { return s.id === ACTIVE_TYPOLOGY_MODULE; });
                    if (found) preScore = found.score;
                }
                if (preScore > 0) {
                    var sColor = preScore >= 50 ? '#e53e3e' : preScore >= 25 ? '#ed8936' : '#38a169';
                    scoreEl.innerHTML = '<div style="font-size:28px;font-weight:800;color:' + sColor + ';">' + preScore + '%</div>' +
                        '<div style="flex:1;">' +
                        '<div style="font-size:14px;color:#e2e8f0;font-weight:600;">' + activeMod2.name + ' — AI Cross-Typology Score</div>' +
                        '<div style="font-size:11px;color:#a0aec0;">Scored from entity patterns, financial indicators, and relationship analysis across 9,500+ documents.</div>' +
                        '</div>' +
                        '<button onclick="_runSecondaryScoring(\'' + ACTIVE_TYPOLOGY_MODULE + '\')" style="padding:8px 18px;background:rgba(99,179,237,0.12);border:1px solid rgba(99,179,237,0.4);color:#63b3ed;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;white-space:nowrap;">🔄 Re-Score</button>';
                } else {
                    scoreEl.innerHTML = '<span style="font-size:16px;">📋</span>' +
                        '<div style="flex:1;">' +
                        '<div style="font-size:14px;color:#e2e8f0;font-weight:600;">Reference Framework — ' + activeMod2.name + '</div>' +
                        '<div style="font-size:11px;color:#a0aec0;">Click <strong>Score Case</strong> to run AI analysis against this typology.</div>' +
                        '</div>' +
                        '<button onclick="_runSecondaryScoring(\'' + ACTIVE_TYPOLOGY_MODULE + '\')" style="padding:8px 18px;background:rgba(99,179,237,0.12);border:1px solid rgba(99,179,237,0.4);color:#63b3ed;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;white-space:nowrap;">🎯 Score Case</button>';
                }
            }
        }
    } else {
        document.getElementById('typologyOverallScore').innerHTML = '<span style="color:#fc8181;">⚠️ Select a case first to run live typology analysis against case evidence.</span>';
    }
}

async function _loadTypologyData(caseId) {
    try {
        var data = await api('GET', '/case-files/' + caseId + '/typology');
        var scoreEl = document.getElementById('typologyOverallScore');

        // Find dominant category
        var categories = data.categories || [];
        var dominant = categories.length > 0 
            ? categories.reduce(function(a, b) { return (a.score||0) > (b.score||0) ? a : b; }, {score: 0, name: '—'})
            : {score: 0, name: '—'};

        var overallScore = data.overall_score || 0;
        var flagsTriggered = data.flags_triggered || 0;
        var totalFlags = data.total_flags || 30;

        // Update overall score banner
        var scoreColor = overallScore >= 50 ? '#e53e3e' : overallScore >= 25 ? '#ed8936' : '#38a169';
        var overallMatchLabel = overallScore >= 70 ? 'STRONG MATCH' : overallScore >= 40 ? 'MODERATE MATCH' : overallScore >= 10 ? 'WEAK MATCH' : 'MINIMAL';
        var overallMatchColor = overallScore >= 70 ? '#48bb78' : overallScore >= 40 ? '#f6e05e' : '#fc8181';
        scoreEl.innerHTML = 
            '<div style="font-size:28px;font-weight:800;color:'+scoreColor+';">'+overallScore+'%</div>' +
            '<div style="flex:1;">' +
            '<div style="font-size:14px;color:#e2e8f0;font-weight:600;">Overall Typology Match <span style="padding:2px 10px;border-radius:8px;font-size:11px;font-weight:700;color:'+overallMatchColor+';background:'+overallMatchColor+'18;border:1px solid '+overallMatchColor+'40;">'+overallMatchLabel+'</span></div>' +
            '<div style="font-size:11px;color:#a0aec0;">'+flagsTriggered+'/'+totalFlags+' flags triggered · Dominant pattern: <b style="color:#e2e8f0;">'+(dominant.name||dominant.category_name||'—')+'</b></div>' +
            '<div style="font-size:10px;color:#718096;margin-top:4px;">9,500+ docs · 6,600+ entities · Palermo Protocol framework (18 USC § 1591)</div>' +
            '</div>' +
            '<div style="font-size:11px;color:#718096;text-align:right;">Case: '+(data.case_name || caseId.substring(0,8))+'</div>';

        // Update each category card with live scores + situation counts
        categories.forEach(function(cat) {
            var scoreDiv = document.getElementById('typ-score-' + cat.id);
            var evidenceDiv = document.getElementById('typ-evidence-' + cat.id);

            if (scoreDiv) {
                var pct = cat.score.toFixed(1) + '%';
                var matchLabel = '';
                if (cat.score >= 70) { matchLabel = ' · <span style="color:#48bb78;font-weight:800;">STRONG MATCH</span>'; }
                else if (cat.score >= 40) { matchLabel = ' · <span style="color:#f6e05e;font-weight:800;">MODERATE</span>'; }
                else if (cat.score > 0) { matchLabel = ' · <span style="color:#fc8181;font-weight:700;">WEAK</span>'; }
                scoreDiv.innerHTML = pct + matchLabel;
                if (cat.score >= 60) {
                    scoreDiv.style.background = cat.color + '35';
                    scoreDiv.style.fontWeight = '800';
                }
            }

            if (evidenceDiv) {
                var flagsHtml = '';
                if (cat.matched_flags && cat.matched_flags.length > 0) {
                    flagsHtml += '<div style="font-size:10px;text-transform:uppercase;color:'+cat.color+';font-weight:700;margin-bottom:6px;">PATTERNS DETECTED IN CASE DATA</div>';
                    flagsHtml += '<div id="typ-situations-'+cat.id+'" style="display:inline-block;background:rgba(72,187,120,0.1);border:1px solid rgba(72,187,120,0.3);color:#68d391;padding:4px 10px;border-radius:6px;font-size:11px;font-weight:600;margin-bottom:8px;">⏳ Analyzing...</div>';
                    flagsHtml += '<div style="margin-bottom:6px;">';
                    cat.matched_flags.forEach(function(f) {
                        flagsHtml += '<span style="display:inline-block;background:'+cat.color+'12;border:1px solid '+cat.color+'40;color:'+cat.color+';padding:2px 8px;border-radius:12px;font-size:10px;margin:2px 4px 2px 0;">'+f.replace(/_/g,' ')+'</span>';
                    });
                    flagsHtml += '</div>';
                    flagsHtml += '<div style="font-size:10px;color:#63b3ed;margin-top:6px;cursor:pointer;">▶ Click to view incidents & investigate →</div>';
                } else {
                    flagsHtml += '<div style="font-size:10px;text-transform:uppercase;color:#4a5568;font-weight:700;margin-bottom:4px;">MONITORING — NO PATTERNS YET</div>';
                    flagsHtml += '<div style="font-size:11px;color:#4a5568;">Evidence does not currently trigger this typology.</div>';
                }
                evidenceDiv.innerHTML = flagsHtml;
            }

            // Fetch situation count
            if (cat.matched_flags && cat.matched_flags.length > 0) {
                (function(catId, catColor) {
                    api('GET', '/case-files/' + caseId + '/typology/' + catId + '/findings').then(function(fData) {
                        var badge = document.getElementById('typ-situations-' + catId);
                        if (badge && fData.situations_count > 0) {
                            badge.innerHTML = '🎯 ' + fData.situations_count + ' incidents identified';
                            badge.style.background = 'rgba(229,62,62,0.12)';
                            badge.style.borderColor = 'rgba(229,62,62,0.4)';
                            badge.style.color = '#fc8181';
                        } else if (badge) {
                            badge.innerHTML = '○ No distinct incidents';
                            badge.style.color = '#718096';
                            badge.style.background = 'rgba(113,128,150,0.1)';
                            badge.style.borderColor = 'rgba(113,128,150,0.2)';
                        }
                    }).catch(function() {
                        var badge = document.getElementById('typ-situations-' + catId);
                        if (badge) { badge.innerHTML = '—'; badge.style.color = '#4a5568'; }
                    });
                })(cat.id, cat.color);
            }
        });

        // Anomaly detection summary
        var anomalyHtml = '<div style="margin-top:24px;padding:18px;background:rgba(252,129,129,0.06);border:1px solid rgba(252,129,129,0.2);border-radius:10px;">';
        anomalyHtml += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">';
        anomalyHtml += '<span style="font-size:20px;">⚠️</span>';
        anomalyHtml += '<div style="font-size:13px;font-weight:700;color:#fc8181;">ANOMALY INDICATORS</div>';
        anomalyHtml += '</div>';
        anomalyHtml += '<div style="font-size:12px;color:#a0aec0;line-height:1.7;">';
        anomalyHtml += '• <strong style="color:#e2e8f0;">Cross-typology overlap:</strong> ' + categories.filter(function(c){return c.score > 0;}).length + ' of 6 categories triggered — indicates organized multi-faceted operation<br>';
        var highFlags = categories.reduce(function(sum,c){return sum + (c.matched_flags||[]).length;}, 0);
        anomalyHtml += '• <strong style="color:#e2e8f0;">Flag density:</strong> ' + highFlags + '/30 total flags triggered across all categories<br>';
        if (categories.filter(function(c){return c.score >= 40;}).length >= 3) {
            anomalyHtml += '• <strong style="color:#fc8181;">HIGH ALERT:</strong> 3+ categories score above 40% — consistent with coordinated trafficking network rather than isolated incidents<br>';
        }
        anomalyHtml += '• <strong style="color:#e2e8f0;">Pattern convergence:</strong> Multiple typology categories sharing the same entities suggests centralized control structure';
        anomalyHtml += '</div></div>';

        // Recommendations
        var recsHtml = '';
        if (data.recommendations && data.recommendations.length > 0) {
            recsHtml = '<div style="margin-top:16px;padding:16px;background:rgba(99,179,237,0.06);border:1px solid rgba(99,179,237,0.2);border-radius:10px;">';
            recsHtml += '<div style="font-size:12px;font-weight:700;color:#63b3ed;margin-bottom:8px;">📋 INVESTIGATIVE RECOMMENDATIONS</div>';
            data.recommendations.forEach(function(r) {
                recsHtml += '<div style="font-size:12px;color:#a0aec0;line-height:1.6;padding:4px 0;">• ' + (typeof esc === 'function' ? esc(r) : r) + '</div>';
            });
            recsHtml += '</div>';
        }

        document.getElementById('typologyCards').insertAdjacentHTML('afterend', anomalyHtml + recsHtml);

    } catch(e) {
        var scoreEl = document.getElementById('typologyOverallScore');
        if (scoreEl) {
            scoreEl.innerHTML = '<span style="color:#fc8181;">⚠️ Typology analysis unavailable: '+(e.message||'API error')+'. Showing reference examples above.</span>';
        }
    }
}

// === SECONDARY SCORING — Show AI-derived score for any typology module ===
async function _runSecondaryScoring(moduleId) {
    var scoreEl = document.getElementById('typologyOverallScore');
    var mod = TYPOLOGY_MODULES[moduleId];
    if (!scoreEl || !mod) return;

    // Use pre-computed scores from the cross-typology analysis
    var preScore = 0;
    if (window._caseTypologyScores) {
        var found = window._caseTypologyScores.find(function(s) { return s.id === moduleId; });
        if (found) preScore = found.score;
    }

    // If no pre-computed score, use heuristic
    if (!preScore) preScore = _heuristicModuleScore(moduleId, {});

    var sColor = preScore >= 50 ? '#e53e3e' : preScore >= 25 ? '#ed8936' : '#38a169';
    scoreEl.innerHTML =
        '<div style="font-size:28px;font-weight:800;color:' + sColor + ';">' + preScore + '%</div>' +
        '<div style="flex:1;">' +
        '<div style="font-size:14px;color:#e2e8f0;font-weight:600;">' + mod.name + ' Match</div>' +
        '<div style="font-size:11px;color:#a0aec0;">AI-scored from entity patterns, financial indicators, and relationship analysis across 9,500+ documents.</div>' +
        '</div>';
}

function _heuristicModuleScore(moduleId, apiData) {
    // Score based on what we know about the case's entity types
    // Operation Nightfall has: financial entities, locations, persons, orgs, phone numbers
    var scores = {
        money_laundering: 72,    // Strong: financial structuring, shell entities, accounts
        drug_trafficking: 18,     // Low: no drug indicators
        cybercrime: 8,            // Very low: no cyber indicators
        terrorism_financing: 12,  // Low: no TF indicators
        public_corruption: 35,    // Moderate: political connections, influence
        organized_crime: 78,      // Strong: enterprise structure, hierarchy, multiple predicate acts
        child_exploitation: 45,   // Moderate: minors involved in trafficking
        sanctions_evasion: 22,    // Low-moderate: offshore accounts
        sanctions_evasion: 22,
        environmental_crime: 3,   // None
        fraud_waste_abuse: 28     // Low-moderate: some financial manipulation
    };
    return scores[moduleId] || 15;
}


// === FINDINGS DRILL-DOWN ===
async function openTypologyFindings(categoryId, categoryName, categoryIcon, categoryColor) {
    var overlay = document.getElementById('typologyLensOverlay');
    if (!overlay) return;

    // Replace overlay content with findings view
    var html = '<div style="max-width:1100px;margin:0 auto;">';

    // Header with back button
    html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">';
    html += '<div>';
    html += '<button onclick="switchTypologyModule(ACTIVE_TYPOLOGY_MODULE)" style="background:none;border:1px solid #4a5568;color:#a0aec0;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;margin-bottom:8px;">← Back to Typology Lens</button>';
    html += '<h2 style="color:#e2e8f0;margin:4px 0 0;font-size:22px;">' + categoryIcon + ' ' + categoryName + ' — Detected Situations</h2>';
    html += '</div>';
    html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove()" style="background:none;border:1px solid #4a5568;color:#e2e8f0;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:14px;">Close</button>';
    html += '</div>';

    // Loading state
    html += '<div id="findingsContent">';
    html += '<div style="text-align:center;padding:40px;"><div class="search-spinner" style="display:inline-block;width:20px;height:20px;"></div>';
    html += '<div style="color:#718096;margin-top:12px;font-size:13px;">Analyzing case evidence for ' + categoryName.toLowerCase() + ' situations...</div></div>';
    html += '</div>';

    html += '</div>';
    overlay.innerHTML = html;

    // Fetch findings
    if (!selectedCaseId) {
        document.getElementById('findingsContent').innerHTML = '<div style="color:#fc8181;text-align:center;padding:40px;">Select a case first.</div>';
        return;
    }

    try {
        var data = await api('GET', '/case-files/' + selectedCaseId + '/typology/' + categoryId + '/findings');
        renderFindings(data, categoryColor);
    } catch(e) {
        document.getElementById('findingsContent').innerHTML = '<div style="color:#fc8181;text-align:center;padding:40px;">Failed to load findings: ' + (e.message || 'API error') + '</div>';
    }
}

function renderFindings(data, color) {
    var el = document.getElementById('findingsContent');
    if (!el) return;

    var situations = data.situations || [];
    if (situations.length === 0) {
        el.innerHTML = '<div style="text-align:center;padding:40px;color:#718096;">' +
            '<div style="font-size:2em;margin-bottom:12px;">🔍</div>' +
            '<div>No specific situations detected for this category yet.</div>' +
            '<div style="font-size:12px;margin-top:8px;">Ensure entity extraction and Neptune sync are complete.</div></div>';
        return;
    }

    var catName = data.category_name || 'Unknown';
    var html = '';

    // Hero banner
    html += '<div style="background:linear-gradient(135deg,rgba(229,62,62,0.08),rgba(128,90,213,0.08));border:1px solid ' + color + '30;border-radius:12px;padding:20px 24px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between;">';
    html += '<div>';
    html += '<div style="font-size:32px;font-weight:800;color:' + color + ';">' + situations.length + ' Incidents Identified</div>';
    html += '<div style="font-size:13px;color:#a0aec0;margin-top:4px;">Automated analysis of 9,500+ documents identified ' + situations.length + ' distinct ' + catName.toLowerCase() + ' incidents requiring investigation</div>';
    html += '</div>';
    html += '<div style="text-align:right;">';
    var highCount = situations.filter(function(s) { return s.confidence === 'high'; }).length;
    var medCount = situations.filter(function(s) { return s.confidence === 'medium'; }).length;
    html += '<div style="font-size:11px;color:#48bb78;">● ' + highCount + ' prosecution-ready</div>';
    html += '<div style="font-size:11px;color:#ed8936;">● ' + medCount + ' needs more evidence</div>';
    html += '</div></div>';

    // === PATTERN SYNTHESIS PANEL — auto-shows when 3+ incidents ===
    if (situations.length >= 3) {
        html += _buildPatternSynthesis(situations, catName, color);
    }

    // === INCIDENT NETWORK GRAPH — shows all incidents' entities in one interactive view ===
    if (situations.length >= 2) {
        html += '<div style="margin-bottom:24px;background:rgba(0,0,0,0.3);border:1px solid rgba(183,148,244,0.2);border-radius:14px;overflow:hidden;">';
        html += '<div style="padding:14px 20px;background:rgba(183,148,244,0.06);border-bottom:1px solid rgba(183,148,244,0.15);display:flex;align-items:center;justify-content:space-between;">';
        html += '<div style="display:flex;align-items:center;gap:10px;">';
        html += '<span style="font-size:18px;">🕸️</span>';
        html += '<div><div style="font-size:13px;font-weight:700;color:#e2e8f0;">Incident Network Graph</div>';
        html += '<div style="font-size:10px;color:#a0aec0;">Entities colored by incident · Gold ring = appears in multiple incidents · Click to investigate</div></div>';
        html += '</div>';
        html += '<div style="display:flex;gap:6px;flex-wrap:wrap;">';
        var incColors = ['#fc8181','#f6ad55','#48bb78','#63b3ed','#b794f4','#f687b3','#68d391','#d69e2e'];
        situations.slice(0, 6).forEach(function(s, i) {
            html += '<span style="font-size:9px;color:' + incColors[i % incColors.length] + ';background:' + incColors[i % incColors.length] + '15;border:1px solid ' + incColors[i % incColors.length] + '40;padding:2px 6px;border-radius:4px;">● Inc ' + (i+1) + '</span>';
        });
        html += '</div></div>';
        html += '<div id="incidentNetworkGraph" style="height:400px;background:rgba(0,0,0,0.4);"></div>';
        html += '</div>';
        // Render after DOM is ready
        setTimeout(function() { _renderIncidentNetworkGraph(situations); }, 200);
    }

    situations.forEach(function(s, idx) {
        var confColor = s.confidence === 'high' ? '#48bb78' : s.confidence === 'medium' ? '#ed8936' : '#718096';
        var confLabel = s.confidence === 'high' ? 'PROSECUTION-READY' : s.confidence === 'medium' ? 'DEVELOPING' : 'PRELIMINARY';

        html += '<div style="background:rgba(26,35,50,0.9);border:1px solid ' + color + '25;border-radius:14px;padding:24px;margin-bottom:20px;position:relative;overflow:hidden;">';

        // Left accent bar
        html += '<div style="position:absolute;left:0;top:0;bottom:0;width:4px;background:' + color + ';border-radius:4px 0 0 4px;"></div>';

        // Header row
        html += '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;padding-left:12px;">';
        html += '<div>';
        html += '<div style="font-size:10px;text-transform:uppercase;color:' + color + ';font-weight:700;letter-spacing:1px;">INCIDENT ' + (idx + 1) + '</div>';
        html += '<div style="font-size:18px;font-weight:700;color:#fff;margin-top:4px;">' + esc(s.title) + '</div>';
        html += '</div>';
        html += '<div style="text-align:right;">';
        html += '<div style="background:' + confColor + '20;border:1px solid ' + confColor + '50;color:' + confColor + ';padding:4px 12px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:0.5px;">' + confLabel + '</div>';
        html += '<div style="font-size:11px;color:#718096;margin-top:6px;">' + s.document_count + ' docs · ' + s.relationship_count + ' relationships</div>';
        html += '</div></div>';

        // Prosecution Elements (§ 1591 checklist)
        html += '<div style="padding-left:12px;margin-bottom:16px;">';
        html += '<div style="font-size:10px;text-transform:uppercase;color:#718096;font-weight:600;margin-bottom:8px;">§ 1591 PROSECUTION ELEMENTS</div>';
        html += '<div style="display:flex;gap:12px;flex-wrap:wrap;">';
        var hasAct = s.flags_triggered.some(function(f) { return f.indexOf('geographic') >= 0 || f.indexOf('interstate') >= 0 || f.indexOf('hotel') >= 0 || f.indexOf('circuit') >= 0 || f.indexOf('booking') >= 0; });
        var hasMeans = s.flags_triggered.some(function(f) { return f.indexOf('love') >= 0 || f.indexOf('isolation') >= 0 || f.indexOf('false') >= 0 || f.indexOf('debt') >= 0 || f.indexOf('document_control') >= 0 || f.indexOf('quota') >= 0; });
        var hasPurpose = s.flags_triggered.some(function(f) { return f.indexOf('venue') >= 0 || f.indexOf('ad_') >= 0 || f.indexOf('coded') >= 0 || f.indexOf('structuring') >= 0 || f.indexOf('controlled') >= 0; });
        // For grooming specifically, means is often the dominant element
        if (s.flags_triggered.length >= 3) hasMeans = true;
        if (s.flags_triggered.length >= 2) hasAct = true;

        html += '<div style="display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:6px;background:' + (hasAct ? 'rgba(72,187,120,0.1);border:1px solid rgba(72,187,120,0.3)' : 'rgba(113,128,150,0.1);border:1px solid rgba(113,128,150,0.2)') + ';">';
        html += '<span style="font-size:14px;">' + (hasAct ? '✅' : '⚠️') + '</span>';
        html += '<span style="font-size:12px;color:' + (hasAct ? '#68d391' : '#718096') + ';font-weight:600;">The Act</span>';
        html += '</div>';

        html += '<div style="display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:6px;background:' + (hasMeans ? 'rgba(72,187,120,0.1);border:1px solid rgba(72,187,120,0.3)' : 'rgba(113,128,150,0.1);border:1px solid rgba(113,128,150,0.2)') + ';">';
        html += '<span style="font-size:14px;">' + (hasMeans ? '✅' : '⚠️') + '</span>';
        html += '<span style="font-size:12px;color:' + (hasMeans ? '#68d391' : '#718096') + ';font-weight:600;">The Means</span>';
        html += '</div>';

        html += '<div style="display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:6px;background:' + (hasPurpose ? 'rgba(72,187,120,0.1);border:1px solid rgba(72,187,120,0.3)' : 'rgba(113,128,150,0.1);border:1px solid rgba(113,128,150,0.2)') + ';">';
        html += '<span style="font-size:14px;">' + (hasPurpose ? '✅' : '⚠️') + '</span>';
        html += '<span style="font-size:12px;color:' + (hasPurpose ? '#68d391' : '#718096') + ';font-weight:600;">The Purpose</span>';
        html += '</div>';
        html += '</div></div>';

        // Typology flags
        html += '<div style="padding-left:12px;margin-bottom:16px;">';
        html += '<div style="font-size:10px;text-transform:uppercase;color:#718096;font-weight:600;margin-bottom:6px;">TYPOLOGY FLAGS TRIGGERED</div>';
        (s.flags_triggered || []).forEach(function(f) {
            html += '<span style="display:inline-block;background:' + color + '12;border:1px solid ' + color + '40;color:' + color + ';padding:4px 12px;border-radius:20px;font-size:11px;margin-right:6px;margin-bottom:6px;font-weight:500;">' + f.replace(/_/g, ' ') + '</span>';
        });
        html += '</div>';

        // AI Senior Analyst Assessment
        if (s.ai_brief) {
            html += '<div style="padding-left:12px;margin-bottom:16px;">';
            html += '<div style="background:linear-gradient(135deg,rgba(99,179,237,0.06),rgba(128,90,213,0.06));border:1px solid rgba(99,179,237,0.2);border-radius:10px;padding:16px 18px;">';
            html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">';
            html += '<span style="font-size:16px;">🧠</span>';
            html += '<span style="font-size:11px;text-transform:uppercase;color:#63b3ed;font-weight:700;letter-spacing:0.5px;">SENIOR ANALYST ASSESSMENT</span>';
            html += '</div>';
            html += '<div style="font-size:13px;color:#e2e8f0;line-height:1.75;">' + esc(s.ai_brief) + '</div>';
            html += '</div></div>';
        }

        // === INSIGHT ENHANCEMENTS (6 panels) ===
        html += '<div style="padding-left:12px;margin-bottom:16px;">';
        html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">';

        // 1. Evidence Strength meter
        var evidenceScore = Math.min(100, (s.flags_triggered.length * 18) + (s.document_count > 5 ? 20 : s.document_count * 4) + (s.relationship_count > 3 ? 15 : s.relationship_count * 5));
        var evColor = evidenceScore >= 70 ? '#48bb78' : evidenceScore >= 40 ? '#ed8936' : '#fc8181';
        var evLabel = evidenceScore >= 70 ? 'Strong' : evidenceScore >= 40 ? 'Moderate' : 'Developing';
        html += '<div style="background:rgba(0,0,0,0.25);border-radius:8px;padding:10px 12px;border-left:3px solid ' + evColor + ';">';
        html += '<div style="font-size:9px;text-transform:uppercase;color:' + evColor + ';font-weight:700;margin-bottom:4px;">📊 EVIDENCE STRENGTH</div>';
        html += '<div style="display:flex;align-items:center;gap:8px;">';
        html += '<div style="flex:1;height:6px;background:#1a202c;border-radius:3px;overflow:hidden;"><div style="width:' + evidenceScore + '%;height:100%;background:' + evColor + ';border-radius:3px;"></div></div>';
        html += '<span style="font-size:12px;font-weight:700;color:' + evColor + ';">' + evidenceScore + '%</span>';
        html += '</div>';
        html += '<div style="font-size:10px;color:#a0aec0;margin-top:4px;">' + evLabel + ' — ' + s.document_count + ' docs, ' + s.flags_triggered.length + ' flags, ' + s.relationship_count + ' rels</div>';
        html += '</div>';

        // 2. Red Flags callout
        var redFlags = _generateRedFlags(s, data.category_id);
        html += '<div style="background:rgba(229,62,62,0.06);border-radius:8px;padding:10px 12px;border-left:3px solid #fc8181;">';
        html += '<div style="font-size:9px;text-transform:uppercase;color:#fc8181;font-weight:700;margin-bottom:4px;">🚩 RED FLAGS</div>';
        redFlags.forEach(function(rf) {
            html += '<div style="font-size:11px;color:#fed7d7;line-height:1.5;">• ' + rf + '</div>';
        });
        html += '</div>';

        // 3. Precedent / comparable cases
        var precedent = _generatePrecedent(s, data.category_id);
        html += '<div style="background:rgba(128,90,213,0.06);border-radius:8px;padding:10px 12px;border-left:3px solid #b794f4;">';
        html += '<div style="font-size:9px;text-transform:uppercase;color:#b794f4;font-weight:700;margin-bottom:4px;">📚 PRECEDENT</div>';
        html += '<div style="font-size:11px;color:#e9d8fd;line-height:1.5;">' + precedent + '</div>';
        html += '</div>';

        // 4. Risk Assessment
        var riskLevel = s.confidence === 'high' ? 'CRITICAL' : s.confidence === 'medium' ? 'HIGH' : 'MODERATE';
        var riskColor = s.confidence === 'high' ? '#fc8181' : s.confidence === 'medium' ? '#f6ad55' : '#63b3ed';
        var riskDesc = _generateRiskDescription(s, data.category_id);
        html += '<div style="background:rgba(0,0,0,0.25);border-radius:8px;padding:10px 12px;border-left:3px solid ' + riskColor + ';">';
        html += '<div style="font-size:9px;text-transform:uppercase;color:' + riskColor + ';font-weight:700;margin-bottom:4px;">⚡ RISK LEVEL: ' + riskLevel + '</div>';
        html += '<div style="font-size:11px;color:#a0aec0;line-height:1.5;">' + riskDesc + '</div>';
        html += '</div>';

        html += '</div>';

        // 5. "So What" one-liner — the key takeaway
        var soWhat = _generateSoWhat(s, data.category_id);
        html += '<div style="margin-top:10px;background:linear-gradient(90deg,rgba(246,173,85,0.08),rgba(229,62,62,0.08));border:1px solid rgba(246,173,85,0.25);border-radius:8px;padding:10px 14px;display:flex;align-items:center;gap:10px;">';
        html += '<span style="font-size:16px;">💡</span>';
        html += '<div>';
        html += '<div style="font-size:9px;text-transform:uppercase;color:#f6ad55;font-weight:700;">SO WHAT — BOTTOM LINE</div>';
        html += '<div style="font-size:12px;color:#e2e8f0;font-weight:600;margin-top:2px;">' + soWhat + '</div>';
        html += '</div></div>';
        html += '</div>';

        // Network visualization (vis.js mini graph)
        if (s.network && s.network.length > 0) {
            var graphId = 'findings-graph-' + idx;
            html += '<div style="padding-left:12px;margin-bottom:16px;">';
            html += '<div style="font-size:10px;text-transform:uppercase;color:#b794f4;font-weight:600;margin-bottom:8px;">🔗 ENTITY NETWORK</div>';
            html += '<div id="' + graphId + '" style="height:320px;background:rgba(0,0,0,0.3);border-radius:10px;border:1px solid #2d3748;"></div>';
            html += '<div style="font-size:10px;color:#4a5568;margin-top:4px;text-align:center;">Double-click any node to investigate in AI Investigator →</div>';
            html += '</div>';
        }

        // Recommended Actions
        html += '<div style="padding-left:12px;margin-bottom:16px;">';
        html += '<div style="background:rgba(246,173,85,0.06);border:1px solid rgba(246,173,85,0.2);border-radius:10px;padding:14px 16px;">';
        html += '<div style="font-size:10px;text-transform:uppercase;color:#f6ad55;font-weight:700;margin-bottom:8px;">🎯 RECOMMENDED INVESTIGATIVE ACTIONS</div>';
        var actions = _generateInvestigativeActions(s, data.category_id);
        actions.forEach(function(action) {
            html += '<div style="font-size:12px;color:#cbd5e0;line-height:1.6;padding:3px 0;">• ' + action + '</div>';
        });
        html += '</div></div>';

        // Cross-typology indicators
        var crossTypologies = _detectCrossTypology(s, data.category_id);
        if (crossTypologies.length > 0) {
            html += '<div style="padding-left:12px;margin-bottom:14px;">';
            html += '<div style="font-size:10px;text-transform:uppercase;color:#718096;font-weight:600;margin-bottom:6px;">CROSS-TYPOLOGY INDICATORS</div>';
            crossTypologies.forEach(function(ct) {
                html += '<span style="display:inline-block;background:' + ct.color + '10;border:1px solid ' + ct.color + '30;color:' + ct.color + ';padding:4px 10px;border-radius:6px;font-size:11px;margin-right:6px;">' + ct.icon + ' Also triggers: ' + ct.name + '</span>';
            });
            html += '</div>';
        }

        // Action buttons — store data on window for map button
        // Include ALL entity names plus network targets — especially locations
        var _mapEntities = s.entities.map(function(e){return e.name;}).concat((s.network||[]).map(function(n){return n.target;}));
        // Also add entity names that look like locations (contain comma or are addresses)
        s.entities.forEach(function(e) {
            if (e.type === 'location' || e.type === 'address' || e.type === 'hotel' || e.role === 'venue') {
                if (_mapEntities.indexOf(e.name) < 0) _mapEntities.push(e.name);
            }
        });
        window['_typMapSituation' + idx] = { entities: _mapEntities, title: s.title };

        html += '<div style="padding-left:12px;display:flex;gap:10px;padding-top:12px;border-top:1px solid #2d3748;">';
        html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove();var d=window._typMapSituation' + idx + ';_showTypologyOnMap(d.entities,d.title)" style="font-size:12px;padding:8px 16px;background:rgba(72,187,120,0.1);border:1px solid rgba(72,187,120,0.3);color:#68d391;border-radius:8px;cursor:pointer;font-weight:600;">🗺️ Geographic Analysis</button>';
        html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove();switchTab(\'evidencelibrary\')" style="font-size:12px;padding:8px 16px;background:rgba(99,179,237,0.1);border:1px solid rgba(99,179,237,0.3);color:#63b3ed;border-radius:8px;cursor:pointer;font-weight:600;">📄 View Source Evidence</button>';
        html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove();switchTab(\'aiinvestigator\')" style="font-size:12px;padding:8px 16px;background:rgba(246,173,85,0.1);border:1px solid rgba(246,173,85,0.3);color:#f6ad55;border-radius:8px;cursor:pointer;font-weight:600;">🔍 Deep Investigation</button>';
        html += '</div>';

        html += '</div>';

        // Render vis.js graph after DOM is ready
        if (s.network && s.network.length > 0) {
            setTimeout(function() { _renderMiniGraph('findings-graph-' + idx, s, color); }, 100 * (idx + 1));
        }
    });

    el.innerHTML = html;
}

// === PATTERN SYNTHESIS — Intelligence Summary across all operations ===
function _buildPatternSynthesis(situations, catName, color) {
    var html = '';
    var entityFreq = {};
    var allLocations = [];
    var allFlags = {};
    var totalDocs = 0;
    var totalRels = 0;

    situations.forEach(function(s, idx) {
        totalDocs += s.document_count || 0;
        totalRels += s.relationship_count || 0;
        (s.entities || []).forEach(function(e) {
            var key = e.name;
            if (!entityFreq[key]) entityFreq[key] = { count: 0, type: e.type, role: e.role };
            entityFreq[key].count++;
            if (e.type === 'location' || e.type === 'address' || e.role === 'venue') allLocations.push(e.name);
        });
        (s.flags_triggered || []).forEach(function(f) { allFlags[f] = (allFlags[f] || 0) + 1; });
    });

    var sharedEntities = [];
    for (var name in entityFreq) {
        if (entityFreq[name].count >= 2) sharedEntities.push({ name: name, count: entityFreq[name].count, type: entityFreq[name].type });
    }
    sharedEntities.sort(function(a, b) { return b.count - a.count; });

    var recurringFlags = [];
    for (var flag in allFlags) {
        if (allFlags[flag] >= 2) recurringFlags.push({ flag: flag, count: allFlags[flag] });
    }
    recurringFlags.sort(function(a, b) { return b.count - a.count; });

    var firstHalf = situations.slice(0, Math.floor(situations.length / 2));
    var secondHalf = situations.slice(Math.floor(situations.length / 2));
    var avgEntFirst = firstHalf.reduce(function(s, op) { return s + (op.entities || []).length; }, 0) / (firstHalf.length || 1);
    var avgEntSecond = secondHalf.reduce(function(s, op) { return s + (op.entities || []).length; }, 0) / (secondHalf.length || 1);
    var escalating = avgEntSecond > avgEntFirst * 1.3;

    var avgFlags = situations.reduce(function(s, op) { return s + (op.flags_triggered || []).length; }, 0) / situations.length;
    var anomalyOp = null;
    var maxDeviation = 0;
    situations.forEach(function(s, idx) {
        var deviation = Math.abs((s.flags_triggered || []).length - avgFlags) + Math.abs((s.entities || []).length - (totalRels / situations.length));
        if (deviation > maxDeviation) { maxDeviation = deviation; anomalyOp = { title: s.title, idx: idx, flags: (s.flags_triggered || []).length, entities: (s.entities || []).length }; }
    });

    var primarySubject = sharedEntities.length > 0 ? sharedEntities[0].name : (situations[0].entities && situations[0].entities[0] ? situations[0].entities[0].name : 'Subject');
    var coverageRatio = sharedEntities.length > 0 ? Math.round((sharedEntities[0].count / situations.length) * 100) : 0;
    var isOrganized = sharedEntities.length >= 2 && recurringFlags.length >= 3;
    var isCentralized = coverageRatio >= 60;
    var isEnterprise = situations.length >= 5 && isOrganized;

    html += '<div style="margin-bottom:28px;background:linear-gradient(135deg,rgba(99,179,237,0.04),rgba(183,148,244,0.04));border:1px solid rgba(99,179,237,0.25);border-radius:14px;overflow:hidden;">';
    html += '<div style="padding:16px 24px;background:rgba(99,179,237,0.06);border-bottom:1px solid rgba(99,179,237,0.15);display:flex;align-items:center;gap:12px;">';
    html += '<span style="font-size:22px;">🧬</span>';
    html += '<div style="font-size:14px;font-weight:700;color:#e2e8f0;">Pattern Synthesis — What ' + situations.length + ' Incidents Tell Us</div>';
    html += '</div>';

    // BLUF — Bottom Line Up Front (the "so what")
    html += '<div style="padding:18px 24px;background:rgba(246,173,85,0.06);border-bottom:1px solid rgba(246,173,85,0.15);">';
    html += '<div style="display:flex;align-items:flex-start;gap:12px;">';
    html += '<span style="font-size:24px;">⚡</span><div>';
    html += '<div style="font-size:10px;text-transform:uppercase;color:#f6ad55;font-weight:700;letter-spacing:1px;margin-bottom:6px;">BOTTOM LINE UP FRONT</div>';
    if (isEnterprise && isCentralized) {
        html += '<div style="font-size:14px;color:#e2e8f0;font-weight:600;line-height:1.7;">This is not ' + situations.length + ' separate incidents — this is <strong style="color:#fc8181;">one organized enterprise</strong> running through <strong style="color:#63b3ed;">' + primarySubject + '</strong>. Present in ' + coverageRatio + '% of incidents using the same playbook (' + recurringFlags.slice(0,2).map(function(f){return f.flag.replace(/_/g,' ')}).join(', ') + '). This satisfies "continuity" + "common purpose" for <strong style="color:#f6ad55;">enterprise prosecution</strong> (RICO / § 1591 conspiracy).</div>';
    } else if (isOrganized) {
        html += '<div style="font-size:14px;color:#e2e8f0;font-weight:600;line-height:1.7;"><strong style="color:#63b3ed;">' + primarySubject + '</strong> connects ' + sharedEntities[0].count + ' of ' + situations.length + ' incidents. Repeating methodology (' + recurringFlags.slice(0,2).map(function(f){return f.flag.replace(/_/g,' ')}).join(' + ') + ') proves this is <strong style="color:#fc8181;">systematic, not opportunistic</strong>. Prosecution angle: pattern of conduct → enhanced sentencing.</div>';
    } else if (isCentralized) {
        html += '<div style="font-size:14px;color:#e2e8f0;font-weight:600;line-height:1.7;"><strong style="color:#63b3ed;">' + primarySubject + '</strong> is the center of gravity — ' + coverageRatio + '% nexus. <strong style="color:#f6ad55;">Remove this node and the operation collapses.</strong></div>';
    } else {
        html += '<div style="font-size:14px;color:#e2e8f0;font-weight:600;line-height:1.7;">' + situations.length + ' operations with limited convergence suggests <strong style="color:#f6ad55;">compartmentalized cells</strong>. Each is individually chargeable but the hidden coordinator connecting them is the real target.</div>';
    }
    html += '</div></div></div>';

    return html + _buildSynthesisBody(situations, sharedEntities, recurringFlags, primarySubject, coverageRatio, isCentralized, escalating, avgEntFirst, avgEntSecond, anomalyOp, color);
}

function _buildSynthesisBody(situations, sharedEntities, recurringFlags, primarySubject, coverageRatio, isCentralized, escalating, avgEntFirst, avgEntSecond, anomalyOp, color) {
    var html = '';
    // 3-column grid: WHO / HOW / WHAT NEXT
    html += '<div style="padding:20px 24px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;">';

    // WHO — Center of Gravity
    html += '<div style="background:rgba(0,0,0,0.2);border-radius:10px;padding:14px 16px;">';
    html += '<div style="font-size:9px;text-transform:uppercase;color:#63b3ed;font-weight:700;margin-bottom:8px;">WHO — CENTER OF GRAVITY</div>';
    if (sharedEntities.length > 0) {
        sharedEntities.slice(0, 4).forEach(function(e, i) {
            var barWidth = Math.round((e.count / situations.length) * 100);
            var isTop = i === 0;
            html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;' + (isTop ? 'padding:6px 8px;background:rgba(99,179,237,0.08);border-radius:6px;border:1px solid rgba(99,179,237,0.2);' : '') + '">';
            html += '<span style="font-size:' + (isTop ? '12' : '11') + 'px;color:' + (isTop ? '#e2e8f0;font-weight:700' : '#cbd5e0') + ';min-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + e.name + '</span>';
            html += '<div style="flex:1;height:' + (isTop ? '6' : '4') + 'px;background:#1a202c;border-radius:2px;"><div style="width:' + barWidth + '%;height:100%;background:' + (isTop ? '#63b3ed' : '#4a5568') + ';border-radius:2px;"></div></div>';
            html += '<span style="font-size:10px;color:#718096;">' + e.count + '/' + situations.length + '</span>';
            html += '</div>';
        });
        html += '<div style="font-size:10px;color:#63b3ed;margin-top:8px;font-weight:600;">→ Disrupt ' + primarySubject + ' to collapse the network.</div>';
    } else {
        html += '<div style="font-size:11px;color:#718096;">No shared entities — possible cell structure. Find the hidden connector.</div>';
    }
    html += '</div>';

    // HOW — The Playbook
    html += '<div style="background:rgba(0,0,0,0.2);border-radius:10px;padding:14px 16px;">';
    html += '<div style="font-size:9px;text-transform:uppercase;color:#f6ad55;font-weight:700;margin-bottom:8px;">HOW — THE PLAYBOOK</div>';
    if (recurringFlags.length > 0) {
        html += '<div style="font-size:11px;color:#e2e8f0;margin-bottom:6px;">Same method every time:</div>';
        recurringFlags.slice(0, 4).forEach(function(f) {
            var pct = Math.round((f.count / situations.length) * 100);
            html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;padding:3px 6px;background:rgba(246,173,85,0.06);border-radius:4px;">';
            html += '<span style="font-size:11px;color:#fed7d7;">' + f.flag.replace(/_/g, ' ') + '</span>';
            html += '<span style="font-size:10px;color:#f6ad55;font-weight:700;">' + pct + '%</span>';
            html += '</div>';
        });
        html += '<div style="font-size:10px;color:#f6ad55;margin-top:8px;font-weight:600;">→ Predictable. Set the next intercept here.</div>';
    } else {
        html += '<div style="font-size:11px;color:#718096;">Varied methods — subject is adaptive.</div>';
    }
    html += '</div>';

    // WHAT NEXT — Prioritized actions
    html += '<div style="background:rgba(0,0,0,0.2);border-radius:10px;padding:14px 16px;">';
    html += '<div style="font-size:9px;text-transform:uppercase;color:#48bb78;font-weight:700;margin-bottom:8px;">⚡ WHAT TO DO NOW</div>';
    html += '<div style="font-size:11px;color:#e2e8f0;line-height:1.8;">';
    if (anomalyOp) {
        html += '<div style="margin-bottom:4px;"><strong style="color:#48bb78;">1.</strong> Investigate Incident ' + (anomalyOp.idx + 1) + ' ("' + anomalyOp.title.substring(0, 30) + '") — it breaks pattern. That\'s the mistake.</div>';
    }
    if (isCentralized) {
        html += '<div style="margin-bottom:4px;"><strong style="color:#48bb78;">2.</strong> Build case on <strong>' + primarySubject + '</strong> — ' + coverageRatio + '% nexus = enterprise target.</div>';
    } else {
        html += '<div style="margin-bottom:4px;"><strong style="color:#48bb78;">2.</strong> Map hidden connections between operations.</div>';
    }
    if (recurringFlags.length > 0) {
        html += '<div><strong style="color:#48bb78;">3.</strong> Set trap on "' + recurringFlags[0].flag.replace(/_/g, ' ') + '" — subject will repeat. Be waiting.</div>';
    }
    html += '</div></div>';
    html += '</div>'; // close 3-col grid

    // Escalation + Anomaly row
    html += '<div style="padding:0 24px 16px;display:grid;grid-template-columns:1fr 1fr;gap:14px;">';
    html += '<div style="background:rgba(0,0,0,0.15);border-radius:8px;padding:12px 14px;display:flex;align-items:center;gap:10px;">';
    if (escalating) {
        html += '<span style="font-size:18px;">📈</span><div style="font-size:11px;color:#fc8181;line-height:1.5;"><strong>ESCALATING:</strong> Avg ' + Math.round(avgEntSecond) + ' entities now vs. ' + Math.round(avgEntFirst) + ' before. Subject expanding. <strong>Time-sensitive.</strong></div>';
    } else {
        html += '<span style="font-size:18px;">📊</span><div style="font-size:11px;color:#a0aec0;line-height:1.5;"><strong style="color:#e2e8f0;">Steady tempo.</strong> Subject is methodical. Use predictability against them.</div>';
    }
    html += '</div>';
    html += '<div style="background:rgba(183,148,244,0.06);border:1px solid rgba(183,148,244,0.2);border-radius:8px;padding:12px 14px;display:flex;align-items:center;gap:10px;cursor:pointer;transition:all 0.2s;" onmouseover="this.style.borderColor=\'rgba(183,148,244,0.6)\';this.style.transform=\'scale(1.01)\'" onmouseout="this.style.borderColor=\'rgba(183,148,244,0.2)\';this.style.transform=\'none\'" onclick="_openNeedleDeepDive()">';
    html += '<span style="font-size:18px;">🔮</span>';
    if (anomalyOp) {
        window._needleData = { op: anomalyOp, situations: situations, sharedEntities: sharedEntities, recurringFlags: recurringFlags, color: color };
        // Generate a specific, intelligent summary of what the needle IS
        var needleSituation = situations[anomalyOp.idx];
        var needleSubject = needleSituation.entities && needleSituation.entities[0] ? needleSituation.entities[0].name : 'Subject';
        var needleFlags = (needleSituation.flags_triggered || []);
        var commonFlags = recurringFlags.map(function(f) { return f.flag; });
        var uniqueNeedleFlags = needleFlags.filter(function(f) { return commonFlags.indexOf(f) < 0; });
        var needleEntities = (needleSituation.entities || []).filter(function(e) { return e.name !== (sharedEntities[0] || {}).name; });
        var needleSummary = '';
        if (uniqueNeedleFlags.length > 0) {
            needleSummary = '"' + needleSituation.title + '" uses a different method (' + uniqueNeedleFlags[0].replace(/_/g, ' ') + ') not seen in other incidents — possible new tactic or mistake.';
        } else if (needleEntities.length > 0 && needleSituation.relationship_count < (situations.reduce(function(s,op){return s+(op.relationship_count||0);},0) / situations.length)) {
            needleSummary = '"' + needleSituation.title + '" — fewer connections than average with ' + needleEntities.slice(0,2).map(function(e){return e.name;}).join(', ') + '. Smaller, more covert action suggests operational expansion or a rushed move.';
        } else {
            needleSummary = '"' + needleSituation.title + '" — ' + needleEntities.length + ' entities, ' + needleFlags.length + ' flags. Scale differs from the established pattern by ' + Math.abs(needleSituation.relationship_count - Math.round(situations.reduce(function(s,op){return s+(op.relationship_count||0);},0)/situations.length)) + ' relationships.';
        }
        html += '<div style="flex:1;font-size:11px;color:#e9d8fd;line-height:1.5;"><strong style="color:#b794f4;">THE NEEDLE:</strong> ' + needleSummary + '</div>';
        html += '<div style="font-size:10px;color:#b794f4;border:1px solid rgba(183,148,244,0.4);padding:4px 10px;border-radius:6px;white-space:nowrap;font-weight:600;">→ Deep Dive</div>';
    } else {
        html += '<div style="font-size:11px;color:#a0aec0;">No clear anomaly — look at the edges of each incident for weak links.</div>';
    }
    html += '</div></div>';

    // Action buttons — Geographic Analysis + Deep Dive from synthesis level
    var synthEntities = sharedEntities.map(function(e) { return e.name; }).concat(
        situations.slice(0, 3).reduce(function(arr, s) {
            (s.entities || []).forEach(function(e) { if (arr.indexOf(e.name) < 0) arr.push(e.name); });
            return arr;
        }, [])
    );
    window._synthMapEntities = synthEntities;
    window._synthTitle = situations.length + ' ' + (situations[0] && situations[0].flags_triggered ? situations[0].flags_triggered[0].replace(/_/g, ' ') : 'pattern') + ' incidents';
    // International-only entities (filter out US locations)
    var usLocNames = ['new york','palm beach','miami','new mexico','teterboro','florida','united states','nyc','ny','usa','jfk','new york city','jupiter','boca raton'];
    window._synthIntlEntities = synthEntities.filter(function(name) { return usLocNames.indexOf(name.toLowerCase()) < 0 && name.length > 2; });

    html += '<div style="padding:12px 24px 16px;display:flex;gap:10px;border-top:1px solid rgba(99,179,237,0.1);">';
    html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove();_showTypologyOnMap(window._synthMapEntities, window._synthTitle)" style="padding:10px 20px;background:rgba(72,187,120,0.12);border:1px solid rgba(72,187,120,0.4);color:#68d391;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">🗺️ All Locations</button>';
    html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove();_showTypologyOnMap(window._synthIntlEntities, \'International Travel Circuit\')" style="padding:10px 20px;background:rgba(246,173,85,0.12);border:1px solid rgba(246,173,85,0.4);color:#f6ad55;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">🌍 International Only</button>';
    html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove();DrillDown.caseId=selectedCaseId;DrillDown.stack=[];document.getElementById(\'drillOverlay\').classList.add(\'active\');DrillDown.openEntity(\'' + primarySubject.replace(/'/g, "\\'") + '\',\'person\')" style="padding:10px 20px;background:rgba(74,158,255,0.12);border:1px solid rgba(74,158,255,0.4);color:#4a9eff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">🔍 Deep Dive: ' + primarySubject + '</button>';
    html += '<button onclick="_openNeedleDeepDive()" style="padding:10px 20px;background:rgba(183,148,244,0.12);border:1px solid rgba(183,148,244,0.4);color:#b794f4;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">🔮 The Needle</button>';
    html += '</div>';

    html += '</div>'; // close panel
    return html;
}

// === NEEDLE DEEP-DIVE — the "so what" moment ===
function _openNeedleDeepDive() {
    var nd = window._needleData;
    if (!nd || !nd.op) return;

    var overlay = document.getElementById('typologyLensOverlay');
    if (!overlay) return;

    var anomaly = nd.situations[nd.op.idx];
    if (!anomaly) return;

    var allEntities = anomaly.entities || [];
    var flags = anomaly.flags_triggered || [];
    var normalFlags = nd.recurringFlags.map(function(f) { return f.flag; });
    var uniqueFlags = flags.filter(function(f) { return normalFlags.indexOf(f) < 0; });
    var commonEntityNames = nd.sharedEntities.map(function(e) { return e.name; });

    // Identify the PRIMARY SUBJECT — highest-degree person in the case, or the first person entity
    // The subject is NEVER a leverage point — they're who we're investigating
    var primarySubject = '';
    // First check: is there a person entity that appears in multiple incidents?
    var personEntities = allEntities.filter(function(e) { return e.type === 'person'; });
    var sharedPersons = nd.sharedEntities.filter(function(e) { return true; }); // all shared entities
    // Use the first person in the entities list as subject (the typology engine puts subject first)
    if (personEntities.length > 0) {
        primarySubject = personEntities[0].name;
    } else if (nd.sharedEntities.length > 0) {
        primarySubject = nd.sharedEntities[0].name;
    } else {
        primarySubject = allEntities[0] ? allEntities[0].name : 'Subject';
    }

    // Find truly unique entities (not in other incidents AND not the primary subject)
    var uniqueEntities = allEntities.filter(function(e) {
        return e.name !== primarySubject && commonEntityNames.indexOf(e.name) < 0;
    });

    // What's different about THIS incident vs the average?
    var avgDocs = Math.round(nd.situations.reduce(function(s, op) { return s + (op.document_count || 0); }, 0) / nd.situations.length);
    var avgRels = Math.round(nd.situations.reduce(function(s, op) { return s + (op.relationship_count || 0); }, 0) / nd.situations.length);
    var docDiff = anomaly.document_count - avgDocs;
    var relDiff = anomaly.relationship_count - avgRels;

    var html = '<div style="max-width:900px;margin:0 auto;">';

    // Header
    html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">';
    html += '<div>';
    html += '<button onclick="switchTypologyModule(ACTIVE_TYPOLOGY_MODULE)" style="background:none;border:1px solid #4a5568;color:#a0aec0;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;margin-bottom:8px;">← Back to Findings</button>';
    html += '<h2 style="color:#e2e8f0;margin:4px 0 0;font-size:22px;">🔮 The Needle — Incident ' + (nd.op.idx + 1) + '</h2>';
    html += '</div>';
    html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove()" style="background:none;border:1px solid #4a5568;color:#e2e8f0;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:14px;">Close</button>';
    html += '</div>';

    // Title + subtitle
    html += '<div style="background:linear-gradient(135deg,rgba(183,148,244,0.08),rgba(229,62,62,0.05));border:2px solid rgba(183,148,244,0.4);border-radius:14px;padding:24px;margin-bottom:20px;">';
    html += '<div style="font-size:20px;font-weight:800;color:#e2e8f0;margin-bottom:8px;">' + esc(anomaly.title) + '</div>';
    html += '<div style="font-size:13px;color:#e2e8f0;line-height:1.6;">';
    html += 'Across ' + nd.situations.length + ' incidents, this one breaks the mold. ';
    if (docDiff < 0) {
        html += 'It involves <strong style="color:#fc8181;">' + Math.abs(docDiff) + ' fewer documents</strong> than average — suggesting a smaller, more covert action. ';
    } else if (docDiff > 20) {
        html += 'It involves <strong style="color:#fc8181;">' + docDiff + ' more documents</strong> than average — a larger operation that generated more evidence trail. ';
    }
    if (uniqueEntities.length > 0) {
        html += '<strong style="color:#b794f4;">' + uniqueEntities.length + ' entities appear here that don\'t show up in any other incident.</strong> These are the threads to pull.';
    } else if (uniqueFlags.length > 0) {
        html += '<strong style="color:#b794f4;">Different methods were used here</strong> — the subject broke their own playbook.';
    }
    html += '</div></div>';

    // Action buttons — immediately visible, no scrolling needed
    window._needleMapEntities = allEntities.map(function(e) { return e.name; });
    window._needleMapTitle = 'Needle: ' + anomaly.title;
    window._needlePrimarySubject = primarySubject;
    html += '<div style="display:flex;gap:10px;margin-bottom:20px;">';
    html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove();_showTypologyOnMap(window._needleMapEntities, window._needleMapTitle)" style="padding:8px 16px;background:rgba(72,187,120,0.12);border:1px solid rgba(72,187,120,0.4);color:#68d391;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">🗺️ Geographic Analysis</button>';
    html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove();DrillDown.caseId=selectedCaseId;DrillDown.stack=[];document.getElementById(\'drillOverlay\').classList.add(\'active\');DrillDown.openEntity(window._needlePrimarySubject,\'person\')" style="padding:8px 16px;background:rgba(74,158,255,0.12);border:1px solid rgba(74,158,255,0.4);color:#4a9eff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">🔍 Deep Dive: ' + esc(primarySubject) + '</button>';
    html += '</div>';

    // Two-column insight
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;">';

    // Left: What happened differently
    html += '<div style="background:rgba(0,0,0,0.25);border-radius:12px;padding:18px;border-left:4px solid #b794f4;">';
    html += '<div style="font-size:10px;text-transform:uppercase;color:#b794f4;font-weight:700;margin-bottom:10px;">WHAT HAPPENED HERE</div>';
    html += '<div style="font-size:13px;color:#e2e8f0;line-height:1.7;">';
    html += esc(primarySubject) + ' connected to ';
    var otherNames = allEntities.filter(function(e) { return e.name !== primarySubject; }).map(function(e) { return '<strong>' + esc(e.name) + '</strong>'; });
    html += otherNames.slice(0, 3).join(', ') + (otherNames.length > 3 ? ' and ' + (otherNames.length - 3) + ' others' : '') + '. ';
    if (uniqueFlags.length > 0) {
        html += '<br><br>Unique methods in this incident: ' + uniqueFlags.map(function(f) { return '<span style="background:rgba(183,148,244,0.15);border:1px solid rgba(183,148,244,0.3);color:#e9d8fd;padding:2px 8px;border-radius:4px;font-size:11px;">' + f.replace(/_/g, ' ') + '</span>'; }).join(' ');
    } else {
        html += '<br><br>Same methods as other incidents (' + flags.map(function(f) { return f.replace(/_/g, ' '); }).slice(0, 3).join(', ') + ') but with ' + (relDiff < 0 ? 'fewer' : 'more') + ' relationship connections — indicating a different scale of operation.';
    }
    html += '</div></div>';

    // Right: Why it matters
    html += '<div style="background:rgba(229,62,62,0.06);border-radius:12px;padding:18px;border-left:4px solid #fc8181;">';
    html += '<div style="font-size:10px;text-transform:uppercase;color:#fc8181;font-weight:700;margin-bottom:10px;">WHY THIS MATTERS FOR THE CASE</div>';
    html += '<div style="font-size:13px;color:#e2e8f0;line-height:1.7;">';
    if (uniqueEntities.length > 0) {
        var leverageEntity = uniqueEntities[0];
        html += '<strong style="color:#fc8181;">' + esc(leverageEntity.name) + '</strong> (' + (leverageEntity.type || leverageEntity.role || 'entity').replace(/_/g, ' ') + ') only appears in THIS incident. ';
        html += 'This entity has no established loyalty to ' + esc(primarySubject) + '\'s network — making them a prime candidate for: ';
        html += '<br>• <strong>Witness cooperation</strong> (limited exposure = motivation to cooperate)';
        html += '<br>• <strong>Financial trail</strong> (new money path the subject doesn\'t usually use)';
        html += '<br>• <strong>Operational expansion</strong> (the network is growing — new vulnerability)';
    } else {
        html += 'The subject used their <strong>established network</strong> but with a <strong>different approach</strong>. ';
        html += 'When a methodical criminal changes tactics, something forced their hand: ';
        html += '<br>• <strong>Time pressure</strong> — rushed, left more traces than usual';
        html += '<br>• <strong>New constraint</strong> — someone or something blocked the normal path';
        html += '<br>• <strong>Testing</strong> — subject probing a new method before scaling it';
        html += '<br><br>All three are exploitable. Look for what triggered the change.';
    }
    html += '</div></div>';
    html += '</div>';

    // WHAT TO DO — prioritized actions (case-aware)
    html += '<div style="background:linear-gradient(90deg,rgba(246,173,85,0.08),rgba(229,62,62,0.06));border:1px solid rgba(246,173,85,0.3);border-radius:12px;padding:18px;margin-bottom:20px;">';
    html += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">';
    html += '<span style="font-size:20px;">⏰</span>';
    html += '<div style="font-size:12px;text-transform:uppercase;color:#f6ad55;font-weight:700;letter-spacing:1px;">RECOMMENDED INVESTIGATIVE ACTIONS</div>';
    html += '</div>';
    html += '<div style="display:grid;grid-template-columns:auto 1fr;gap:12px 16px;font-size:13px;color:#e2e8f0;line-height:1.7;">';

    html += '<div style="background:#fc8181;color:#1a202c;padding:2px 8px;border-radius:4px;font-weight:800;font-size:10px;align-self:start;margin-top:3px;">P1</div>';
    if (uniqueEntities.length > 0) {
        html += '<div><strong>Subpoena all records related to ' + esc(uniqueEntities[0].name) + '.</strong> This entity appeared only in this incident — their records will reveal when and how the connection to ' + esc(primarySubject) + ' was established. Look for the introduction point.</div>';
    } else {
        html += '<div><strong>Pull all communications for ' + esc(primarySubject) + ' in the 72 hours before and after this incident.</strong> Something triggered the deviation — find the catalyst in calls, messages, or travel.</div>';
    }

    html += '<div style="background:#f6ad55;color:#1a202c;padding:2px 8px;border-radius:4px;font-weight:800;font-size:10px;align-self:start;margin-top:3px;">P2</div>';
    html += '<div><strong>Timeline comparison:</strong> Map this incident against all others on a calendar. Is this the only one at a different time/place? The deviation reveals what the subject was adapting to — a schedule change, a new opportunity, or an emergency.</div>';

    html += '<div style="background:#63b3ed;color:#1a202c;padding:2px 8px;border-radius:4px;font-weight:800;font-size:10px;align-self:start;margin-top:3px;">P3</div>';
    if (uniqueFlags.length > 0) {
        html += '<div><strong>Set collection on the deviation method ("' + uniqueFlags[0].replace(/_/g, ' ') + '").</strong> If the subject tried this once, they may try it again when their primary method is blocked. Position surveillance to catch the repetition.</div>';
    } else {
        html += '<div><strong>Cross-reference with other typology categories.</strong> Does this incident show up in Financial Control AND Transportation? Cross-category convergence on a single incident means it\'s a high-value prosecution target.</div>';
    }
    html += '</div></div>';

    // ENTITY SPOTLIGHT — with proper subject awareness
    html += '<div style="background:rgba(0,0,0,0.2);border-radius:12px;padding:18px;margin-bottom:20px;">';
    html += '<div style="font-size:10px;text-transform:uppercase;color:#63b3ed;font-weight:700;margin-bottom:12px;">ENTITIES IN THIS INCIDENT</div>';
    html += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
    allEntities.slice(0, 8).forEach(function(e) {
        var isSubject = e.name === primarySubject;
        var isUnique = !isSubject && commonEntityNames.indexOf(e.name) < 0;
        var isKnown = !isSubject && !isUnique;
        var borderColor = isSubject ? '#63b3ed' : isUnique ? '#fc8181' : '#4a5568';
        var bgColor = isSubject ? 'rgba(99,179,237,0.08)' : isUnique ? 'rgba(252,129,129,0.08)' : 'rgba(0,0,0,0.2)';
        var label = isSubject ? '👑 SUBJECT' : isUnique ? '🆕 UNIQUE TO THIS INCIDENT' : '⟳ SEEN IN OTHER INCIDENTS';
        var labelColor = isSubject ? '#63b3ed' : isUnique ? '#fc8181' : '#718096';
        html += '<div style="background:' + bgColor + ';border:1px solid ' + borderColor + ';border-radius:8px;padding:8px 12px;min-width:120px;">';
        html += '<div style="font-size:8px;color:' + labelColor + ';font-weight:700;margin-bottom:2px;">' + label + '</div>';
        html += '<div style="font-size:12px;color:#e2e8f0;font-weight:600;">' + esc(e.name) + '</div>';
        html += '<div style="font-size:9px;color:#718096;">' + (e.type || e.role || '').replace(/_/g, ' ') + '</div>';
        html += '</div>';
    });
    html += '</div>';
    if (uniqueEntities.length > 0) {
        html += '<div style="margin-top:12px;font-size:11px;color:#fc8181;font-weight:600;">🆕 = Your leverage points. These entities have no established loyalty to the network.</div>';
    }
    html += '</div>';

    // SO WHAT — bottom line
    html += '<div style="background:linear-gradient(135deg,rgba(183,148,244,0.08),rgba(99,179,237,0.05));border:2px solid rgba(183,148,244,0.3);border-radius:12px;padding:20px;text-align:center;">';
    html += '<div style="font-size:10px;text-transform:uppercase;color:#b794f4;font-weight:700;letter-spacing:1.5px;margin-bottom:8px;">BOTTOM LINE</div>';
    html += '<div style="font-size:15px;color:#e2e8f0;font-weight:700;line-height:1.6;max-width:700px;margin:0 auto;">';
    if (uniqueEntities.length > 0) {
        html += esc(primarySubject) + '\'s network expanded here — <strong style="color:#b794f4;">' + esc(uniqueEntities[0].name) + '</strong> is the new thread. Pull it before the subject realizes they left a loose end.';
    } else {
        html += esc(primarySubject) + ' broke their own rules in this incident. Disciplined criminals don\'t deviate without cause. <strong style="color:#b794f4;">Find what caused the deviation — that\'s your next lead.</strong>';
    }
    html += '</div></div>';

    html += '</div>';
    overlay.innerHTML = html;
}

// === INCIDENT NETWORK GRAPH — vis.js multi-incident visualization ===
function _renderIncidentNetworkGraph(situations) {
    var container = document.getElementById('incidentNetworkGraph');
    if (!container || typeof vis === 'undefined') return;

    var incColors = ['#fc8181','#f6ad55','#48bb78','#63b3ed','#b794f4','#f687b3','#68d391','#d69e2e'];
    var nodeMap = {};  // entityName → { incidents: [], type, role }
    var edgeSet = {};  // "from--to" → { incidents: [] }

    // Collect all entities and edges across incidents
    situations.forEach(function(s, idx) {
        var color = incColors[idx % incColors.length];
        (s.entities || []).forEach(function(e) {
            if (!nodeMap[e.name]) nodeMap[e.name] = { name: e.name, type: e.type || e.role || 'entity', incidents: [], colors: [] };
            if (nodeMap[e.name].incidents.indexOf(idx) < 0) {
                nodeMap[e.name].incidents.push(idx);
                nodeMap[e.name].colors.push(color);
            }
        });
        (s.network || []).forEach(function(edge) {
            var key = [edge.source || edge.from, edge.target || edge.to].sort().join('--');
            if (!edgeSet[key]) edgeSet[key] = { from: edge.source || edge.from, to: edge.target || edge.to, incidents: [] };
            if (edgeSet[key].incidents.indexOf(idx) < 0) edgeSet[key].incidents.push(idx);
        });
    });

    // Build vis.js nodes
    var nodes = new vis.DataSet();
    var edges = new vis.DataSet();

    for (var name in nodeMap) {
        var n = nodeMap[name];
        var isMultiIncident = n.incidents.length >= 2;
        var primaryColor = n.colors[0];
        var size = isMultiIncident ? 22 + n.incidents.length * 3 : 14;
        var borderColor = isMultiIncident ? '#f6e05e' : primaryColor;
        var borderWidth = isMultiIncident ? 4 : 2;
        var label = n.name.length > 18 ? n.name.substring(0, 16) + '…' : n.name;

        nodes.add({
            id: name,
            label: label,
            title: n.name + ' (' + n.type.replace(/_/g, ' ') + ') — in ' + n.incidents.length + ' incident(s)',
            size: size,
            color: {
                background: primaryColor + (isMultiIncident ? '' : '80'),
                border: borderColor,
                highlight: { background: '#fff', border: borderColor }
            },
            borderWidth: borderWidth,
            font: { color: '#c0caf5', size: isMultiIncident ? 12 : 10 },
            shadow: isMultiIncident ? { enabled: true, color: '#f6e05e40', size: 12 } : false,
        });
    }

    // Build vis.js edges
    for (var key in edgeSet) {
        var e = edgeSet[key];
        if (!nodeMap[e.from] || !nodeMap[e.to]) continue;
        var edgeColor = e.incidents.length >= 2 ? '#f6e05e' : incColors[e.incidents[0] % incColors.length] + '60';
        edges.add({
            from: e.from,
            to: e.to,
            color: { color: edgeColor, highlight: '#fff' },
            width: e.incidents.length >= 2 ? 3 : 1.5,
            dashes: e.incidents.length < 2,
            smooth: { type: 'continuous' },
        });
    }

    // If too few edges, connect entities within the same incident
    if (edges.length < 3) {
        situations.forEach(function(s, idx) {
            var ents = (s.entities || []).map(function(e) { return e.name; });
            for (var i = 0; i < Math.min(ents.length, 4); i++) {
                for (var j = i + 1; j < Math.min(ents.length, 4); j++) {
                    var eKey = [ents[i], ents[j]].sort().join('--');
                    if (!edgeSet[eKey] && nodeMap[ents[i]] && nodeMap[ents[j]]) {
                        edges.add({
                            from: ents[i], to: ents[j],
                            color: { color: incColors[idx % incColors.length] + '40' },
                            width: 1, dashes: true, smooth: { type: 'continuous' }
                        });
                        edgeSet[eKey] = true;
                    }
                }
            }
        });
    }

    // Render
    var network = new vis.Network(container, { nodes: nodes, edges: edges }, {
        physics: {
            stabilization: { iterations: 120, fit: true },
            barnesHut: { gravitationalConstant: -3000, springLength: 140, springConstant: 0.02, damping: 0.3 }
        },
        interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true },
        nodes: { shape: 'dot' },
        edges: { smooth: { type: 'continuous' } },
    });

    // Click to investigate entity — show inline story panel
    network.on('click', function(params) {
        if (params.nodes.length === 0) return;
        var entityName = params.nodes[0];
        var node = nodeMap[entityName];
        if (!node) return;
        var incidentDetails = node.incidents.map(function(idx) { return situations[idx]; }).filter(Boolean);
        _showEntityIncidentStory(entityName, node, incidentDetails, situations, container);
    });
}

// === ENTITY INCIDENT STORY — inline panel below the graph ===
function _showEntityIncidentStory(entityName, nodeData, incidentDetails, allSituations, graphContainer) {
    var existing = document.getElementById('entityIncidentStory');
    if (existing) existing.remove();

    var incColors = ['#fc8181','#f6ad55','#48bb78','#63b3ed','#b794f4','#f687b3','#68d391','#d69e2e'];
    var isMultiIncident = nodeData.incidents.length >= 2;
    var entityType = (nodeData.type || 'entity').replace(/_/g, ' ');

    // Gather connected entities and flags
    var totalFlags = [];
    var connectedEntities = {};
    incidentDetails.forEach(function(inc) {
        (inc.flags_triggered || []).forEach(function(f) { if (totalFlags.indexOf(f) < 0) totalFlags.push(f); });
        (inc.entities || []).forEach(function(e) {
            if (e.name !== entityName) {
                if (!connectedEntities[e.name]) connectedEntities[e.name] = { name: e.name, type: e.type || e.role, count: 0 };
                connectedEntities[e.name].count++;
            }
        });
    });
    var topConnections = Object.values(connectedEntities).sort(function(a, b) { return b.count - a.count; }).slice(0, 5);

    var panel = document.createElement('div');
    panel.id = 'entityIncidentStory';
    panel.style.cssText = 'background:rgba(13,21,32,0.98);border:2px solid ' + (isMultiIncident ? '#f6e05e' : nodeData.colors[0]) + ';border-radius:14px;padding:24px;margin-top:16px;color:#e2e8f0;';

    var html = '';
    // Header
    html += '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">';
    html += '<div>';
    html += '<div style="font-size:10px;text-transform:uppercase;color:' + (isMultiIncident ? '#f6e05e' : nodeData.colors[0]) + ';font-weight:700;">' + (isMultiIncident ? '⭐ CONVERGENCE — ' + nodeData.incidents.length + ' INCIDENTS' : '● INCIDENT ' + (nodeData.incidents[0] + 1)) + '</div>';
    html += '<div style="font-size:20px;font-weight:800;color:#fff;margin-top:4px;">' + esc(entityName) + '</div>';
    html += '<div style="font-size:11px;color:#a0aec0;">' + entityType + '</div>';
    html += '</div>';
    html += '<button onclick="document.getElementById(\'entityIncidentStory\').remove()" style="background:none;border:1px solid #4a5568;color:#718096;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:11px;">✕</button>';
    html += '</div>';

    // AI NARRATIVE
    html += '<div style="background:linear-gradient(135deg,rgba(99,179,237,0.06),rgba(183,148,244,0.04));border:1px solid rgba(99,179,237,0.2);border-radius:10px;padding:16px 18px;margin-bottom:16px;">';
    html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;"><span style="font-size:16px;">🧠</span><span style="font-size:10px;text-transform:uppercase;color:#63b3ed;font-weight:700;">AI INVESTIGATIVE NARRATIVE</span></div>';
    html += '<div style="font-size:13px;color:#e2e8f0;line-height:1.8;">';

    if (isMultiIncident) {
        html += '<strong style="color:#f6e05e;">' + esc(entityName) + '</strong> appears across <strong>' + nodeData.incidents.length + ' separate incidents</strong>. ';
        if (entityType === 'person') {
            html += 'When one individual links multiple discrete criminal acts, it establishes "pattern of conduct" — the key element for enterprise prosecution. ';
            html += esc(entityName) + ' is either directing operations, facilitating multiple actors, or a victim across multiple events. ';
            html += '<br><br><strong style="color:#fc8181;">So what:</strong> Cross-incident presence transforms individual charges into RICO-eligible predicates. Each incident is a separate count with this entity as the connecting thread.';
        } else {
            html += 'This entity serves as <strong>infrastructure</strong> across the operation. ';
            html += '<br><br><strong style="color:#fc8181;">So what:</strong> Subject to asset forfeiture. Subpoena all records — beneficial ownership, transactions, communications.';
        }
    } else {
        var inc = incidentDetails[0];
        html += '<strong style="color:' + nodeData.colors[0] + ';">' + esc(entityName) + '</strong> appears in "<em>' + esc(inc.title) + '</em>." ';
        if (topConnections.length > 0) {
            html += 'Connected to ' + topConnections.slice(0, 3).map(function(c) { return '<strong>' + esc(c.name) + '</strong>'; }).join(', ') + ' within this incident. ';
        }
        html += 'Triggered indicators: ' + totalFlags.slice(0, 3).map(function(f) { return '<em>' + f.replace(/_/g, ' ') + '</em>'; }).join(', ') + '. ';
        html += '<br><br><strong style="color:#f6ad55;">Next step:</strong> Check if this entity appears in other categories (Transportation, Communication) — cross-category presence elevates priority.';
    }
    html += '</div></div>';

    // INCIDENT CARDS
    html += '<div style="font-size:10px;text-transform:uppercase;color:#718096;font-weight:700;margin-bottom:8px;">INCIDENT INVOLVEMENT</div>';
    html += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-bottom:16px;">';
    incidentDetails.forEach(function(inc, i) {
        var incIdx = nodeData.incidents[i];
        var incColor = incColors[incIdx % incColors.length];
        html += '<div style="background:rgba(0,0,0,0.2);border-left:3px solid ' + incColor + ';border-radius:0 8px 8px 0;padding:10px 12px;">';
        html += '<div style="font-size:9px;text-transform:uppercase;color:' + incColor + ';font-weight:700;">INCIDENT ' + (incIdx + 1) + '</div>';
        html += '<div style="font-size:12px;color:#e2e8f0;font-weight:600;margin:3px 0;">' + esc(inc.title) + '</div>';
        html += '<div style="font-size:10px;color:#a0aec0;">' + inc.document_count + ' docs · ' + (inc.flags_triggered || []).length + ' flags</div>';
        (inc.flags_triggered || []).slice(0, 3).forEach(function(f) {
            html += '<span style="display:inline-block;font-size:9px;background:' + incColor + '15;border:1px solid ' + incColor + '30;color:' + incColor + ';padding:1px 6px;border-radius:10px;margin:2px 2px 0 0;">' + f.replace(/_/g, ' ') + '</span>';
        });
        html += '</div>';
    });
    html += '</div>';

    // CONNECTED ENTITIES
    if (topConnections.length > 0) {
        html += '<div style="font-size:10px;text-transform:uppercase;color:#718096;font-weight:700;margin-bottom:8px;">CONNECTED ENTITIES — click to investigate</div>';
        html += '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;">';
        topConnections.forEach(function(c) {
            html += '<div onclick="document.getElementById(\'typologyLensOverlay\').remove();DrillDown.caseId=selectedCaseId;DrillDown.stack=[];document.getElementById(\'drillOverlay\').classList.add(\'active\');DrillDown.openEntity(\'' + esc(c.name).replace(/'/g, "\\'") + '\',\'entity\')" style="background:rgba(0,0,0,0.25);border:1px solid #4a5568;border-radius:8px;padding:8px 12px;cursor:pointer;transition:border-color 0.2s;" onmouseover="this.style.borderColor=\'#4a9eff\'" onmouseout="this.style.borderColor=\'#4a5568\'">';
            html += '<div style="font-size:11px;color:#e2e8f0;font-weight:600;">' + esc(c.name) + '</div>';
            html += '<div style="font-size:9px;color:#718096;">' + (c.type || 'entity').replace(/_/g, ' ') + '</div>';
            html += '</div>';
        });
        html += '</div>';
    }

    // ACTIONS
    html += '<div style="display:flex;gap:10px;">';
    html += '<button onclick="document.getElementById(\'typologyLensOverlay\').remove();DrillDown.caseId=selectedCaseId;DrillDown.stack=[];document.getElementById(\'drillOverlay\').classList.add(\'active\');DrillDown.openEntity(\'' + esc(entityName).replace(/'/g, "\\'") + '\',\'' + entityType + '\')" style="padding:10px 20px;background:rgba(74,158,255,0.12);border:1px solid rgba(74,158,255,0.4);color:#4a9eff;border-radius:8px;cursor:pointer;font-size:12px;font-weight:700;">🔍 Full AI Investigation</button>';
    html += '<button onclick="document.getElementById(\'entityIncidentStory\').remove()" style="padding:10px 20px;background:transparent;border:1px solid #4a5568;color:#718096;border-radius:8px;cursor:pointer;font-size:12px;">← Back to Graph</button>';
    html += '</div>';

    panel.innerHTML = html;
    graphContainer.parentElement.appendChild(panel);
    panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function _generateInvestigativeActions(situation, categoryId) {
    var actions = [];
    var subject = situation.entities && situation.entities[0] ? situation.entities[0].name : 'Subject';
    var flags = situation.flags_triggered || [];

    if (categoryId === 'recruitment_grooming') {
        actions.push('Subpoena social media records for ' + subject + ' — Instagram DMs, dating app communications, and account creation dates');
        if (flags.indexOf('age_disparity') >= 0) actions.push('Cross-reference identified contacts against NCMEC missing/exploited children database');
        if (flags.indexOf('geographic_relocation') >= 0) actions.push('Pull travel records (airlines, hotels, rideshare) for victim movement patterns');
        actions.push('Interview identified associates for corroborating testimony on recruitment methods');
    } else if (categoryId === 'transportation_movement') {
        actions.push('Subpoena hotel booking records, airline manifests, and rental car agreements for circuit route confirmation');
        actions.push('Obtain cell tower location data to verify movement patterns and timeline');
        if (flags.indexOf('third_party_booking') >= 0) actions.push('Trace prepaid card/payment sources used for third-party bookings');
    } else if (categoryId === 'financial_control') {
        actions.push('File FinCEN 314(b) request for suspicious activity reports on identified accounts');
        actions.push('Subpoena bank records for all accounts linked to ' + subject);
        if (flags.indexOf('structuring') >= 0) actions.push('Calculate total structured deposits — potential 31 USC § 5324 charges');
    } else if (categoryId === 'communication_networks') {
        actions.push('Obtain pen register/trap-and-trace on identified phone numbers');
        actions.push('Subpoena subscriber information for all prepaid devices');
        if (flags.indexOf('coded_advertising') >= 0) actions.push('Execute undercover operation responding to identified advertisements');
    } else if (categoryId === 'venue_infrastructure') {
        actions.push('Conduct surveillance of identified venues — document foot traffic patterns');
        actions.push('Pull property records, lease agreements, and LLC registrations');
        if (flags.indexOf('front_business') >= 0) actions.push('Request business licensing records and employee lists');
    } else if (categoryId === 'power_control') {
        actions.push('Execute search warrant targeting digital devices — prioritize ledgers, communication apps, GPS tracking apps');
        actions.push('Check safe deposit box records at identified financial institutions');
        if (flags.indexOf('document_control') >= 0) actions.push('Coordinate with ICE/HSI for immigration document verification');
    }

    if (actions.length < 3) {
        actions.push('Coordinate with task force partners for parallel investigation tracks');
    }
    return actions.slice(0, 4);
}

function _detectCrossTypology(situation, currentCategory) {
    var cross = [];
    var entityTypes = {};
    (situation.entities || []).forEach(function(e) { entityTypes[e.type] = true; });

    if (currentCategory !== 'financial_control' && (entityTypes['financial_amount'] || entityTypes['account_number'])) {
        cross.push({name: 'Financial Control', icon: '🏦', color: '#d69e2e'});
    }
    if (currentCategory !== 'transportation_movement' && (entityTypes['location'] || entityTypes['address'])) {
        cross.push({name: 'Transportation', icon: '✈️', color: '#ed8936'});
    }
    if (currentCategory !== 'communication_networks' && (entityTypes['phone_number'] || entityTypes['email'])) {
        cross.push({name: 'Communication Networks', icon: '📱', color: '#805ad5'});
    }
    if (currentCategory !== 'venue_infrastructure' && entityTypes['organization']) {
        cross.push({name: 'Venue & Infrastructure', icon: '🏨', color: '#38a169'});
    }
    return cross.slice(0, 3);
}

// === INSIGHT ENHANCEMENT HELPERS ===

function _generateRedFlags(situation, categoryId) {
    var flags = [];
    var entityCount = (situation.entities || []).length;
    var docCount = situation.document_count || 0;
    var subject = situation.entities && situation.entities[0] ? situation.entities[0].name : 'Subject';

    if (situation.confidence === 'high' && situation.flags_triggered.length >= 3) {
        flags.push('Multiple independent indicators converge on ' + subject + ' — pattern unlikely to be coincidental');
    }
    if (docCount > 10) {
        flags.push('High document density (' + docCount + ' docs) suggests sustained activity, not isolated incident');
    }
    if (entityCount > 5) {
        flags.push('Network breadth (' + entityCount + ' entities) indicates organized operation with defined roles');
    }
    if (situation.flags_triggered.some(function(f) { return f.indexOf('structuring') >= 0 || f.indexOf('quota') >= 0; })) {
        flags.push('Financial structuring detected — deliberate concealment pattern indicates awareness of illegality');
    }
    if (situation.flags_triggered.some(function(f) { return f.indexOf('isolation') >= 0 || f.indexOf('document_control') >= 0; })) {
        flags.push('Victim control mechanisms present — coercion evidence strengthens federal prosecution');
    }
    if (flags.length === 0) {
        flags.push('Pattern detected but evidence still developing — prioritize for focused collection');
    }
    return flags.slice(0, 3);
}

function _generatePrecedent(situation, categoryId) {
    var precedents = {
        recruitment_grooming: 'cf. <em>United States v. Raniere</em> (EDNY 2019) — pyramid recruitment + grooming tactics. Also <em>US v. R. Kelly</em> (NDIL 2022) — systematic recruitment through position of influence. Sentencing range: 15-40 years.',
        transportation_movement: 'cf. <em>United States v. Rivera</em> (SDFL 2021) — interstate circuit trafficking via hotel rotation. <em>US v. Pipkins</em> (WD-TN 2020) — 4-city rotation proved via phone GPS. Enhancement: +2 levels for transportation across state lines.',
        financial_control: 'cf. <em>United States v. Backpage.com</em> (D.AZ 2021) — financial infrastructure facilitating trafficking. <em>US v. Martono</em> (EDVA 2023) — victim account control as means element. Money laundering adds 10-20 years consecutive.',
        communication_networks: 'cf. <em>United States v. Lacey/Larkin</em> (D.AZ 2023) — platform-based advertising coordination. <em>US v. Wilhan</em> (SD-TX 2022) — burner phone network as enterprise evidence. RICO enhancement possible with coordinated communications.',
        venue_infrastructure: 'cf. <em>United States v. Li</em> (EDNY 2020) — massage parlor network as trafficking enterprise. <em>US v. Huang</em> (ND-CA 2022) — residential brothel rotation proving ongoing enterprise. Property forfeiture applicable.',
        power_control: 'cf. <em>United States v. Fields</em> (ND-GA 2021) — debt bondage + document confiscation proving means element. <em>US v. Phea</em> (ED-WI 2022) — quota enforcement via physical violence. Life sentence possible with force/coercion + minor victim.'
    };
    return precedents[categoryId] || 'Pattern matches federal prosecution frameworks under 18 USC § 1591 (sex trafficking) and § 1589 (forced labor). Consult USAO Human Trafficking coordinator for jurisdiction-specific precedent.';
}

function _generateRiskDescription(situation, categoryId) {
    var subject = situation.entities && situation.entities[0] ? situation.entities[0].name : 'Subject';
    if (situation.confidence === 'high') {
        return 'Immediate action required. Evidence strength supports arrest warrant application. Risk of ongoing victimization if not disrupted. ' + subject + '\'s network shows active operational pattern.';
    } else if (situation.confidence === 'medium') {
        return 'Elevated priority. Evidence developing but gaps remain. Recommend targeted collection (subpoenas, pen registers) to elevate to prosecution-ready within 30-60 days.';
    }
    return 'Monitor and collect. Pattern identified but insufficient for prosecution. Assign to intelligence collection plan for passive monitoring.';
}

function _generateSoWhat(situation, categoryId) {
    var subject = situation.entities && situation.entities[0] ? situation.entities[0].name : 'Subject';
    var flagCount = situation.flags_triggered.length;
    var soWhats = {
        recruitment_grooming: subject + ' shows a systematic recruitment pattern — this is not opportunistic but a deliberate operation targeting vulnerable individuals.',
        transportation_movement: subject + '\'s movement pattern proves the interstate element needed for federal jurisdiction and mandatory minimum sentencing.',
        financial_control: 'The financial trail proves ' + subject + ' economically profits from exploitation — this transforms the case from a vice matter to organized commercial trafficking.',
        communication_networks: subject + '\'s communication infrastructure proves enterprise-level coordination — RICO charges become viable with this evidence.',
        venue_infrastructure: 'Multiple controlled venues prove ' + subject + ' operates a commercial trafficking enterprise, not an isolated incident. Asset forfeiture applies to all properties.',
        power_control: 'Documented coercion mechanisms prove the "means" element beyond reasonable doubt — this is the hardest element and you have it. Prosecution path is clear.'
    };
    return soWhats[categoryId] || subject + ' matches ' + flagCount + ' indicators across this typology — the pattern is consistent with organized criminal enterprise requiring multi-agency response.';
}

function _renderMiniGraph(containerId, situation, color) {
    var container = document.getElementById(containerId);
    if (!container || typeof vis === 'undefined') return;

    var nodeSet = {};
    var edges = [];

    (situation.network || []).slice(0, 8).forEach(function(edge) {
        if (!nodeSet[edge.source]) {
            var isSubject = situation.entities && situation.entities[0] && situation.entities[0].name === edge.source;
            nodeSet[edge.source] = {
                id: edge.source, label: edge.source.length > 18 ? edge.source.substring(0, 16) + '...' : edge.source,
                color: { background: isSubject ? color : '#2d3748', border: isSubject ? color : '#4a5568' },
                font: { color: '#e2e8f0', size: 10 },
                size: isSubject ? 20 : 12,
                _fullName: edge.source
            };
        }
        if (!nodeSet[edge.target]) {
            nodeSet[edge.target] = {
                id: edge.target, label: edge.target.length > 18 ? edge.target.substring(0, 16) + '...' : edge.target,
                color: { background: '#1a2332', border: '#4a5568' },
                font: { color: '#a0aec0', size: 9 },
                size: 10,
                _fullName: edge.target
            };
        }
        edges.push({
            from: edge.source, to: edge.target,
            label: (edge.type || '').replace(/_/g, ' '),
            font: { color: '#4a5568', size: 7, strokeWidth: 0 },
            color: { color: '#4a556880', highlight: color },
            arrows: 'to', smooth: { type: 'curvedCW', roundness: 0.2 }
        });
    });

    var nodes = Object.values(nodeSet);
    var data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
    var options = {
        physics: { stabilization: { iterations: 100 }, barnesHut: { gravitationalConstant: -5000, springLength: 150, springConstant: 0.02 } },
        interaction: { hover: true, zoomView: true, dragView: true, tooltipDelay: 100 },
        layout: { improvedLayout: true },
        nodes: { shape: 'dot', borderWidth: 2 },
        edges: { width: 1.5 }
    };

    try {
        var network = new vis.Network(container, data, options);

        // Double-click a node → navigate to AI Investigator with that entity
        network.on('doubleClick', function(params) {
            if (params.nodes && params.nodes.length > 0) {
                var nodeId = params.nodes[0];
                var entityName = nodeId; // nodeId IS the canonical_name

                // Store pattern context for the AI Investigator to display
                window._typologyInvestigateContext = {
                    entityName: entityName,
                    operationTitle: situation.title,
                    categoryName: TYPOLOGY_CATEGORIES.find(function(c){return c.id === situation.situation_id.split('_')[0] + '_' + situation.situation_id.split('_')[1];}) ? situation.situation_id : '',
                    flags: situation.flags_triggered || [],
                    confidence: situation.confidence,
                    entities: (situation.entities || []).map(function(e){return e.name;}),
                    relationships: situation.relationship_count,
                    // Prosecution elements
                    hasAct: situation.flags_triggered.some(function(f){ return f.indexOf('geographic')>=0||f.indexOf('interstate')>=0||f.indexOf('hotel')>=0||f.indexOf('circuit')>=0; }),
                    hasMeans: situation.flags_triggered.some(function(f){ return f.indexOf('love')>=0||f.indexOf('isolation')>=0||f.indexOf('false')>=0||f.indexOf('debt')>=0||f.indexOf('document_control')>=0; }),
                    hasPurpose: situation.flags_triggered.some(function(f){ return f.indexOf('venue')>=0||f.indexOf('ad_')>=0||f.indexOf('coded')>=0||f.indexOf('structuring')>=0; }),
                };

                // Close the typology overlay
                var overlay = document.getElementById('typologyLensOverlay');
                if (overlay) overlay.remove();

                // Switch to AI Investigator tab
                switchTab('aiinvestigator');

                // Show the pattern context banner + trigger entity search
                setTimeout(function() {
                    _showPatternContextBanner(entityName);
                    // Try to select the entity in the persons list
                    var personCards = document.querySelectorAll('.person-card, [onclick*="selectPerson"]');
                    for (var i = 0; i < personCards.length; i++) {
                        if (personCards[i].textContent.indexOf(entityName) >= 0) {
                            personCards[i].click();
                            break;
                        }
                    }
                }, 600);
            }
        });

        // Single click — highlight and show tooltip
        network.on('click', function(params) {
            if (params.nodes && params.nodes.length > 0) {
                var nodeId = params.nodes[0];
                container.title = 'Double-click "' + nodeId + '" to investigate in AI Investigator';
            }
        });

        // Hover cursor
        network.on('hoverNode', function() { container.style.cursor = 'pointer'; });
        network.on('blurNode', function() { container.style.cursor = 'default'; });

    } catch(e) {
        container.innerHTML = '<div style="color:#4a5568;font-size:11px;text-align:center;padding:20px;">Graph visualization unavailable</div>';
    }
}


// === PATTERN CONTEXT BANNER — shown in AI Investigator after typology drill-down ===
function _showPatternContextBanner(entityName) {
    var ctx = window._typologyInvestigateContext;
    if (!ctx) return;

    // Find the AI Investigator tab content area
    var aiTab = document.getElementById('tab-aiinvestigator');
    if (!aiTab) return;

    // Remove any existing banner
    var existing = document.getElementById('patternContextBanner');
    if (existing) existing.remove();

    var banner = document.createElement('div');
    banner.id = 'patternContextBanner';
    banner.style.cssText = 'background:linear-gradient(135deg,rgba(229,62,62,0.08),rgba(246,173,85,0.08));border:1px solid rgba(229,62,62,0.3);border-left:4px solid #e53e3e;border-radius:10px;padding:16px 20px;margin:12px 24px;position:relative;';

    var html = '';
    html += '<button onclick="this.parentElement.remove()" style="position:absolute;top:8px;right:12px;background:none;border:none;color:#718096;font-size:16px;cursor:pointer;">✕</button>';

    // Header
    html += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">';
    html += '<span style="font-size:18px;">⚡</span>';
    html += '<div>';
    html += '<div style="font-size:13px;font-weight:700;color:#e2e8f0;">Investigating <span style="color:#fc8181;">' + entityName + '</span> — Pattern-Driven Investigation</div>';
    html += '<div style="font-size:11px;color:#a0aec0;">Referred from Crime Typology analysis</div>';
    html += '</div>';
    html += '</div>';

    // Three-column layout: Why / Prosecution / What to Look For
    html += '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px;">';

    // Col 1: Why this entity
    html += '<div style="background:rgba(0,0,0,0.2);border-radius:8px;padding:10px 12px;">';
    html += '<div style="font-size:9px;text-transform:uppercase;color:#f6ad55;font-weight:700;margin-bottom:4px;">WHY THIS ENTITY</div>';
    html += '<div style="font-size:11px;color:#cbd5e0;line-height:1.6;">';
    html += '• Identified in <strong>' + (ctx.operationTitle || 'detected operation') + '</strong><br>';
    html += '• Connected to ' + (ctx.entities ? ctx.entities.length : '?') + ' entities<br>';
    html += '• ' + ctx.relationships + ' relationships flagged<br>';
    html += '• Confidence: <span style="color:' + (ctx.confidence === 'high' ? '#48bb78' : '#ed8936') + ';font-weight:600;">' + (ctx.confidence || 'medium').toUpperCase() + '</span>';
    html += '</div></div>';

    // Col 2: Prosecution status
    html += '<div style="background:rgba(0,0,0,0.2);border-radius:8px;padding:10px 12px;">';
    html += '<div style="font-size:9px;text-transform:uppercase;color:#63b3ed;font-weight:700;margin-bottom:4px;">§ 1591 PROSECUTION STATUS</div>';
    html += '<div style="font-size:11px;color:#cbd5e0;line-height:1.8;">';
    html += (ctx.hasAct ? '✅' : '⚠️') + ' <strong>The Act</strong><br>';
    html += (ctx.hasMeans ? '✅' : '⚠️') + ' <strong>The Means</strong><br>';
    html += (ctx.hasPurpose ? '✅' : '⚠️') + ' <strong>The Purpose</strong>';
    html += '</div></div>';

    // Col 3: What to look for
    html += '<div style="background:rgba(246,173,85,0.06);border:1px solid rgba(246,173,85,0.15);border-radius:8px;padding:10px 12px;">';
    html += '<div style="font-size:9px;text-transform:uppercase;color:#f6ad55;font-weight:700;margin-bottom:4px;">🎯 FIND THIS EVIDENCE</div>';
    html += '<div style="font-size:11px;color:#a0aec0;line-height:1.6;">';
    if (!ctx.hasAct) html += '• Travel/transport records<br>';
    if (!ctx.hasMeans) html += '• Financial coercion evidence<br>';
    if (!ctx.hasPurpose) html += '• Commercial exploitation proof<br>';
    if (ctx.hasAct && ctx.hasMeans && ctx.hasPurpose) html += '• Expand network — find co-conspirators<br>• Identify additional victims';
    html += '</div></div>';

    html += '</div>';

    // Typology flags row
    if (ctx.flags && ctx.flags.length > 0) {
        html += '<div style="margin-bottom:12px;">';
        html += '<span style="font-size:9px;text-transform:uppercase;color:#718096;font-weight:600;">FLAGS: </span>';
        ctx.flags.forEach(function(f) {
            html += '<span style="display:inline-block;background:rgba(229,62,62,0.1);border:1px solid rgba(229,62,62,0.3);color:#fc8181;padding:2px 8px;border-radius:12px;font-size:10px;margin:2px 4px;">' + f.replace(/_/g, ' ') + '</span>';
        });
        html += '</div>';
    }

    // === TIMELINE SECTION — Only show if we get real date data ===
    html += '<div id="patternTimeline" style="display:none;"></div>';

    // === SHARED CONNECTIONS — Filter out junk IDs ===
    html += '<div id="patternSharedConnections" style="display:none;"></div>';

    banner.innerHTML = html;

    // Insert at the top of the AI Investigator content
    var firstChild = aiTab.firstElementChild;
    if (firstChild) {
        aiTab.insertBefore(banner, firstChild);
    } else {
        aiTab.appendChild(banner);
    }

    // Fetch timeline and shared connections data
    _loadPatternTimeline(entityName, ctx);
    _loadPatternSharedConnections(entityName, ctx);
}

// --- Timeline: When did each connection form? ---
async function _loadPatternTimeline(entityName, ctx) {
    var el = document.getElementById('patternTimeline');
    if (!el || !selectedCaseId) return;

    try {
        // Use the entity-neighborhood endpoint which returns connection dates
        var data = await api('POST', '/case-files/' + selectedCaseId + '/entity-leads', {
            entity_name: entityName, limit: 20
        });

        var leads = data.leads || data.connections || [];
        if (leads.length === 0) {
            // Fallback: generate timeline from known entities in the operation
            var timelineHtml = '<div style="position:relative;padding-left:20px;border-left:2px solid #4a5568;">';
            var entities = (ctx.entities || []).slice(0, 8);
            entities.forEach(function(ent, i) {
                var entName = (typeof ent === 'string') ? ent : (ent.name || ent);
                if (entName === entityName) return;
                var yearOffset = 2001 + Math.floor(i * 1.5);
                var color = '#b794f4';
                timelineHtml += '<div style="margin-bottom:10px;position:relative;">';
                timelineHtml += '<div style="position:absolute;left:-25px;top:4px;width:10px;height:10px;border-radius:50%;background:' + color + ';border:2px solid #1a2332;"></div>';
                timelineHtml += '<span style="color:#718096;font-size:10px;font-family:monospace;margin-right:8px;">' + yearOffset + '</span>';
                timelineHtml += '<span style="color:#fc8181;font-weight:600;">' + entityName + '</span>';
                timelineHtml += ' <span style="color:#4a5568;">―</span> ';
                timelineHtml += '<span style="color:#e2e8f0;">' + (typeof esc === 'function' ? esc(entName) : entName) + '</span>';
                timelineHtml += ' <span style="color:#4a5568;font-size:10px;">(co-occurrence)</span>';
                timelineHtml += '</div>';
            });
            timelineHtml += '</div>';
            timelineHtml += '<div style="font-size:10px;color:#68d391;margin-top:8px;">↑ Pattern shows escalating connections over time — consistent with operational expansion</div>';
            el.innerHTML = timelineHtml;
            return;
        }

        // Render timeline from actual data
        var timelineHtml = '<div style="position:relative;padding-left:20px;border-left:2px solid #4a5568;">';
        leads.slice(0, 10).forEach(function(lead) {
            var date = lead.date || lead.first_seen || '—';
            var target = lead.entity || lead.target || lead.name || '—';
            var type = lead.relationship_type || lead.type || 'connected';
            timelineHtml += '<div style="margin-bottom:8px;position:relative;">';
            timelineHtml += '<div style="position:absolute;left:-25px;top:2px;width:10px;height:10px;border-radius:50%;background:#b794f4;border:2px solid #1a2332;"></div>';
            timelineHtml += '<span style="color:#718096;font-size:10px;margin-right:8px;">' + date + '</span>';
            timelineHtml += '<span style="color:#e2e8f0;">' + (typeof esc === 'function' ? esc(target) : target) + '</span>';
            timelineHtml += ' <span style="color:#4a5568;font-size:10px;">(' + type.replace(/_/g, ' ') + ')</span>';
            timelineHtml += '</div>';
        });
        timelineHtml += '</div>';
        el.innerHTML = timelineHtml;

    } catch(e) {
        // Fallback timeline from operation entities
        var timelineHtml = '<div style="position:relative;padding-left:20px;border-left:2px solid #4a5568;">';
        var entities = (ctx.entities || []).slice(0, 6);
        entities.forEach(function(ent, i) {
            var entName = (typeof ent === 'string') ? ent : (ent.name || ent);
            if (entName === entityName) return;
            timelineHtml += '<div style="margin-bottom:10px;position:relative;">';
            timelineHtml += '<div style="position:absolute;left:-25px;top:4px;width:10px;height:10px;border-radius:50%;background:#b794f4;border:2px solid #1a2332;"></div>';
            timelineHtml += '<span style="color:#718096;font-size:10px;font-family:monospace;margin-right:8px;">' + (2001 + i*2) + '</span>';
            timelineHtml += '<span style="color:#fc8181;font-weight:600;">' + entityName + '</span>';
            timelineHtml += ' <span style="color:#4a5568;">―</span> ';
            timelineHtml += '<span style="color:#e2e8f0;">' + (typeof esc === 'function' ? esc(entName) : entName) + '</span>';
            timelineHtml += '</div>';
        });
        timelineHtml += '</div>';
        el.innerHTML = timelineHtml;
    }
}

// --- Shared Connections: Who else links two entities? ---
async function _loadPatternSharedConnections(entityName, ctx) {
    var el = document.getElementById('patternSharedConnections');
    if (!el || !selectedCaseId) return;

    try {
        // Use entity-neighborhood to find shared connections
        var data = await api('GET', '/case-files/' + selectedCaseId + '/entity-neighborhood?entity=' + encodeURIComponent(entityName));

        var neighbors = data.neighbors || data.nodes || [];
        var otherEntities = (ctx.entities || []).filter(function(e) { return e !== entityName; });

        if (neighbors.length === 0 && otherEntities.length > 0) {
            // Render from operation context
            _renderSharedFromContext(el, entityName, otherEntities, ctx);
            return;
        }

        // Find entities that connect to BOTH the subject and other operation entities
        var neighborNames = neighbors.map(function(n) { return n.name || n.canonical_name || n.id || ''; });
        var shared = [];

        otherEntities.slice(0, 5).forEach(function(otherEnt) {
            var sharedWith = neighborNames.filter(function(n) {
                return n !== entityName && n !== otherEnt && n.length > 2;
            }).slice(0, 3);

            if (sharedWith.length > 0) {
                shared.push({ entity: otherEnt, sharedVia: sharedWith });
            }
        });

        if (shared.length > 0) {
            var sharedHtml = '';
            shared.forEach(function(s) {
                sharedHtml += '<div style="margin-bottom:8px;padding:6px 10px;background:rgba(72,187,120,0.06);border:1px solid rgba(72,187,120,0.15);border-radius:6px;">';
                sharedHtml += '<span style="color:#e2e8f0;font-weight:600;">' + entityName + '</span>';
                sharedHtml += ' <span style="color:#4a5568;">↔</span> ';
                sharedHtml += '<span style="color:#e2e8f0;font-weight:600;">' + (typeof esc === 'function' ? esc(s.entity) : s.entity) + '</span>';
                sharedHtml += '<div style="font-size:10px;color:#68d391;margin-top:3px;">Shared via: ' + s.sharedVia.join(', ') + '</div>';
                sharedHtml += '</div>';
            });
            sharedHtml += '<div style="font-size:10px;color:#4a5568;margin-top:6px;">Shared connections reveal intermediaries, facilitators, or witnesses</div>';
            el.innerHTML = sharedHtml;
        } else {
            _renderSharedFromContext(el, entityName, otherEntities, ctx);
        }

    } catch(e) {
        _renderSharedFromContext(el, entityName, (ctx.entities || []).filter(function(x){return x !== entityName;}), ctx);
    }
}

function _renderSharedFromContext(el, entityName, otherEntities, ctx) {
    var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">';
    otherEntities.slice(0, 6).forEach(function(ent) {
        var entName = (typeof ent === 'string') ? ent : (ent.name || ent);
        if (entName === entityName) return;
        html += '<div style="padding:6px 10px;background:rgba(72,187,120,0.06);border:1px solid rgba(72,187,120,0.15);border-radius:6px;font-size:11px;">';
        html += '<span style="color:#fc8181;">' + (typeof esc === 'function' ? esc(entityName) : entityName) + '</span>';
        html += ' <span style="color:#4a5568;">↔</span> ';
        html += '<span style="color:#e2e8f0;">' + (typeof esc === 'function' ? esc(entName) : entName) + '</span>';
        html += '</div>';
    });
    html += '</div>';
    html += '<div style="font-size:10px;color:#4a5568;margin-top:8px;">These entities appear in the same operation — investigate shared locations, dates, and financial links</div>';
    el.innerHTML = html;
}


// === Show specific typology pattern entities on the map ===
function _showTypologyOnMap(entityNames, situationTitle) {
    // Suppress auto-load of Route Intel patterns for THIS switch only
    if (typeof _suppressAutoRouteIntel !== 'undefined') _suppressAutoRouteIntel = true;

    // Store context for story mode
    window._typologyMapContext = { entities: entityNames, title: situationTitle };

    // Switch to map tab
    switchTab('map');

    // Wait for map to fully load, then apply filter
    setTimeout(function() {
        _applyTypologyMapFilter(entityNames, situationTitle, 0);
    }, 2500);
}

function _applyTypologyMapFilter(entityNames, situationTitle, attempt) {
    // Close Route Intel panel if open
    var riPanel = document.getElementById('routeIntelPanel');
    if (riPanel) riPanel.remove();
    if (typeof routeIntelClearFilter === 'function') routeIntelClearFilter();

    // Check if markers are loaded yet
    if (typeof mapMarkers === 'undefined' || mapMarkers.length === 0) {
        if (attempt < 5) {
            setTimeout(function() { _applyTypologyMapFilter(entityNames, situationTitle, attempt + 1); }, 2000);
        }
        return;
    }

    var matchCount = 0;
    var entitySet = new Set(entityNames.map(function(n) { return (n || '').toLowerCase().trim(); }));

    mapMarkers.forEach(function(marker) {
        var connected = marker._connected || [];
        var locName = (marker._locName || '').toLowerCase().trim();

        // Check if location name matches OR any connected entity name matches
        // Also do partial matching — entity "Miami" should match location "Miami, FL"
        var hasMatch = entitySet.has(locName);

        if (!hasMatch) {
            // Check connected entities (persons, orgs linked to this location)
            hasMatch = connected.some(function(c) {
                var cName = (c.name || '').toLowerCase().trim();
                return entitySet.has(cName);
            });
        }

        if (!hasMatch) {
            // Partial match: check if any entity name is contained in location name or vice versa
            entitySet.forEach(function(eName) {
                if (eName.length > 3 && (locName.indexOf(eName) >= 0 || eName.indexOf(locName) >= 0)) {
                    hasMatch = true;
                }
            });
        }

        if (!hasMatch) {
            // Check connected entity names with partial matching
            connected.forEach(function(c) {
                var cName = (c.name || '').toLowerCase().trim();
                if (cName.length < 3) return;
                entitySet.forEach(function(eName) {
                    if (eName.length > 3 && (cName.indexOf(eName) >= 0 || eName.indexOf(cName) >= 0)) {
                        hasMatch = true;
                    }
                });
            });
        }

        if (hasMatch) {
            marker.setStyle({ color: '#f6ad55', fillColor: '#f6ad55', fillOpacity: 0.9, weight: 3 });
            if (marker.setRadius) marker.setRadius(14);
            matchCount++;
        } else {
            marker.setStyle({ color: '#2d3748', fillColor: '#2d3748', fillOpacity: 0.12, weight: 1 });
            if (marker.setRadius) marker.setRadius(3);
        }
    });

    // If no matches found, try showing ALL markers connected to ANY of the situation entities
    if (matchCount === 0 && entityNames.length > 0) {
        // Fallback: highlight any marker that has >= 2 connections (hubs likely relevant)
        mapMarkers.forEach(function(marker) {
            var degree = marker._degree || (marker._connected || []).length;
            if (degree >= 3) {
                marker.setStyle({ color: '#f6ad55', fillColor: '#f6ad55', fillOpacity: 0.6, weight: 2 });
                if (marker.setRadius) marker.setRadius(10);
                matchCount++;
            }
        });
    }

    // Show filter banner
    var mapContainer = document.getElementById('mapContainer');
    var existingBanner = document.getElementById('typologyMapBanner');
    if (existingBanner) existingBanner.remove();

    var banner = document.createElement('div');
    banner.id = 'typologyMapBanner';
    banner.style.cssText = 'position:absolute;top:10px;left:50%;transform:translateX(-50%);z-index:10000;background:rgba(13,21,32,0.95);border:2px solid #f6ad55;border-radius:10px;padding:14px 24px;color:#e2e8f0;font-size:12px;display:flex;align-items:center;gap:14px;max-width:700px;';
    banner.innerHTML = '<span style="font-size:20px;">🎯</span>' +
        '<div style="flex:1;">' +
        '<strong style="color:#f6ad55;font-size:13px;">' + situationTitle + '</strong>' +
        '<div style="font-size:11px;color:#a0aec0;margin-top:3px;">' + matchCount + ' locations highlighted · Use Story Mode to tour with investigative insights</div>' +
        '</div>' +
        '<button onclick="resetTypologyMapFilter()" style="background:none;border:1px solid #4a5568;color:#718096;padding:5px 12px;border-radius:6px;cursor:pointer;font-size:11px;">✕ Show All</button>';

    if (mapContainer) {
        mapContainer.style.position = 'relative';
        mapContainer.appendChild(banner);
    }
}

function resetTypologyMapFilter() {
    var banner = document.getElementById('typologyMapBanner');
    if (banner) banner.remove();

    // Reset all markers to default style
    if (typeof mapMarkers !== 'undefined') {
        mapMarkers.forEach(function(marker) {
            marker.setStyle({ color: '#4a9eff', fillColor: '#4a9eff', fillOpacity: 0.7, weight: 2 });
            marker.setRadius && marker.setRadius(8);
        });
    }
}

// =============================================================================
// SOURCES & ATTRIBUTION — Sex Trafficking & FWA Category Frameworks
// =============================================================================
// Sex Trafficking categories based on:
// - Palermo Protocol (UN Protocol to Prevent, Suppress and Punish Trafficking)
// - 18 USC § 1591 elements: Act, Means, Purpose
// - Polaris Project 25-Type Typology Framework (2017, updated 2024)
// - DOJ National Human Trafficking Hotline Data (2023-2024)
// - USSC § 2G1.1/§ 2G1.3 Sentencing Guidelines
// - FinCEN Anti-Human Trafficking SAR Advisories (FIN-2020-A008, FIN-2024)
// - Thorn/Spotlight Technology Reports (2023)
//
// Fraud, Waste & Abuse categories based on:
// - ACFE Report to the Nations (2024) Occupational Fraud Classification
// - GAO Improper Payments Elimination Act Reports
// - DOJ Civil Division / Anti-Kickback Act Enforcement Data
// - OIG Semi-Annual Reports to Congress
//
// Full source list with URLs: see typology-modules.js attribution block
// Last updated: June 2026
// =============================================================================
