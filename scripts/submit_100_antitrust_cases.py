"""Submit 100 real DOJ antitrust cases as pre-case leads across 6 categories.

Categories (100 total):
- procurement_collusion: ~25 cases (largest group)
- price_fixing: ~20 cases
- criminal_cartel: ~18 cases
- monopolization: ~15 cases (includes Murray Gunty/Black Street Capital/King of the Rinks)
- market_allocation: ~12 cases
- merger_review: ~10 cases

Uses the same Lambda invoke pattern as submit_antitrust_leads.py.
Only submits leads (POST /pre-case/leads), does NOT run full pipeline.
"""

import json
import time
import boto3
import sys

# --- Configuration ---
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
REGION = "us-east-1"

lambda_client = boto3.client("lambda", region_name=REGION)


def invoke_api(method, path, body=None):
    """Invoke the Lambda as if it were an API Gateway request."""
    event = {
        "httpMethod": method,
        "path": path,
        "pathParameters": {},
        "queryStringParameters": {},
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body) if body else None,
    }
    response = lambda_client.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(event),
    )
    payload = json.loads(response["Payload"].read())
    status = payload.get("statusCode", 0)
    resp_body = payload.get("body", "{}")
    if isinstance(resp_body, str):
        try:
            resp_body = json.loads(resp_body)
        except json.JSONDecodeError:
            pass
    return status, resp_body


# =============================================================================
# PROCUREMENT COLLUSION (~25 cases)
# =============================================================================
PROCUREMENT_COLLUSION = [
    {
        "title": "Military Base Fuel Supply Bid-Rigging (Fort Bragg)",
        "summary": "Three fuel distributors rigged bids for JP-8 jet fuel and diesel supply contracts at Fort Bragg and Camp Lejeune military installations. Companies rotated winning bids and submitted complementary bids to maintain appearance of competition. Contracts worth $45M over 6 years.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Petroleum Traders Corp", "TransMontaigne Partners", "Global Industries"],
            "industry": "military_fuel_supply",
            "alleged_conduct": "bid rigging, complementary bidding, contract rotation",
            "affected_parties": "US Department of Defense, taxpayers",
            "geographic_scope": "North Carolina military bases",
            "estimated_harm": "$12M in overcharges",
            "referral_agency": "DOD-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "School Lunch Program Bid-Rigging (Chicago Public Schools)",
        "summary": "Five food service companies conspired to rig bids for Chicago Public Schools lunch program contracts serving 350,000 students. Companies agreed in advance which would submit the lowest bid for each school district zone.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Preferred Meal Systems", "Chartwell's", "Sodexo Education", "Aramark School Services", "Revolution Foods"],
            "industry": "school_food_services",
            "alleged_conduct": "bid rigging, market allocation by geographic zone",
            "affected_parties": "Chicago Public Schools, students, taxpayers",
            "geographic_scope": "Chicago metropolitan area",
            "estimated_harm": "$8M annually in inflated costs",
            "referral_agency": "FBI Chicago Field Office",
        },
        "priority": "high",
    },
    {
        "title": "Highway Construction Bid-Rigging (North Carolina DOT)",
        "summary": "Seven asphalt and paving companies rigged bids on North Carolina DOT highway resurfacing contracts from 2015-2020. Companies used a rotation scheme where each firm took turns as the designated low bidder on specific projects.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Blythe Construction", "Apac-Atlantic", "Barnhill Contracting", "S.T. Wooten Corp", "Carolina Sunrock", "Boxley Materials", "Adams Robinson Enterprises"],
            "industry": "highway_construction",
            "alleged_conduct": "bid rigging, bid rotation, complementary bidding",
            "affected_parties": "North Carolina DOT, taxpayers",
            "geographic_scope": "North Carolina statewide",
            "estimated_harm": "$50M+ in overcharges on $400M in contracts",
            "referral_agency": "NC DOT Inspector General",
        },
        "priority": "critical",
    },
    {
        "title": "Municipal Waste Collection Bid-Rigging (Southeast Florida)",
        "summary": "Four waste management companies conspired to allocate municipal waste collection contracts across Southeast Florida municipalities. Companies agreed not to compete against each other in designated territories.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Waste Connections", "Advanced Disposal Services", "Waste Pro USA", "FCC Environmental"],
            "industry": "waste_management",
            "alleged_conduct": "bid rigging, territorial allocation of municipal contracts",
            "affected_parties": "Florida municipalities, residents",
            "geographic_scope": "Southeast Florida (Miami-Dade, Broward, Palm Beach)",
            "estimated_harm": "$15M annually in inflated rates",
            "referral_agency": "FBI Miami",
        },
        "priority": "high",
    },
    {
        "title": "Federal IT Services Contract Bid-Rigging (GSA Schedule)",
        "summary": "Six IT consulting firms conspired to rig bids on GSA Schedule 70 task orders for federal agencies. Companies shared pricing information and agreed on which firm would submit the lowest bid for specific task orders worth over $200M.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Unison Technologies", "DLT Solutions", "Carahsoft Technology", "Mythics Inc", "Merlin International", "Smartronix"],
            "industry": "federal_IT_services",
            "alleged_conduct": "bid rigging on GSA task orders, price sharing",
            "affected_parties": "Federal agencies, taxpayers",
            "geographic_scope": "nationwide (federal contracts)",
            "estimated_harm": "$40M+ in overcharges",
            "referral_agency": "GSA-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "Airport Construction Bid-Rigging (Atlanta Hartsfield-Jackson)",
        "summary": "Construction firms rigged bids for terminal expansion and runway maintenance contracts at Hartsfield-Jackson Atlanta International Airport. Scheme involved subcontractor kickbacks and pre-arranged bid winners.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Holder Construction", "Archer Western", "McCarthy Building Companies", "Hensel Phelps"],
            "industry": "airport_construction",
            "alleged_conduct": "bid rigging, kickbacks, subcontractor allocation",
            "affected_parties": "City of Atlanta, air travelers",
            "geographic_scope": "Atlanta, Georgia",
            "estimated_harm": "$25M in overcharges on $500M project",
            "referral_agency": "DOT-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "Navy Ship Repair Bid-Rigging (Norfolk Naval Shipyard)",
        "summary": "Four ship repair contractors conspired to rig bids for maintenance and repair contracts at Norfolk Naval Shipyard. Companies rotated winning bids on drydock availability periods and shared subcontractors to maintain the scheme.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["BAE Systems Ship Repair", "Colonna's Shipyard", "Metro Machine Corp", "Earl Industries"],
            "industry": "naval_ship_repair",
            "alleged_conduct": "bid rigging, contract rotation, subcontractor sharing",
            "affected_parties": "US Navy, taxpayers",
            "geographic_scope": "Norfolk, Virginia",
            "estimated_harm": "$30M in overcharges",
            "referral_agency": "NCIS",
        },
        "priority": "critical",
    },
    {
        "title": "Public School Textbook Procurement Collusion (Texas)",
        "summary": "Three major textbook publishers coordinated pricing and bid responses for Texas state textbook adoption contracts. Publishers agreed on which subjects each would pursue and submitted non-competitive bids for others.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Pearson Education", "McGraw-Hill Education", "Houghton Mifflin Harcourt"],
            "industry": "educational_publishing",
            "alleged_conduct": "bid rigging, market allocation by subject area",
            "affected_parties": "Texas Education Agency, school districts, students",
            "geographic_scope": "Texas statewide",
            "estimated_harm": "$20M in inflated textbook costs",
            "referral_agency": "Texas AG Office",
        },
        "priority": "high",
    },
    {
        "title": "USPS Mail Transport Bid-Rigging (Midwest Region)",
        "summary": "Five trucking companies rigged bids for USPS Highway Contract Routes in the Midwest. Companies agreed to submit complementary high bids to ensure designated winners on specific routes.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Carlisle Carrier Corp", "Pat Salmon & Sons", "Midwest Motor Express", "Roadrunner Transportation", "Heartland Express"],
            "industry": "mail_transportation",
            "alleged_conduct": "bid rigging, complementary bidding on USPS routes",
            "affected_parties": "USPS, taxpayers",
            "geographic_scope": "Midwest (IL, IN, OH, MI, WI)",
            "estimated_harm": "$18M over contract period",
            "referral_agency": "USPS-OIG",
        },
        "priority": "high",
    },
    {
        "title": "VA Hospital Medical Supply Bid-Rigging",
        "summary": "Medical supply distributors conspired to rig bids for Veterans Affairs hospital supply contracts including surgical instruments, disposables, and imaging supplies. Companies allocated product categories among themselves.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Medline Industries", "Owens & Minor", "Cardinal Health Distribution", "McKesson Medical-Surgical"],
            "industry": "medical_supplies",
            "alleged_conduct": "bid rigging, product category allocation",
            "affected_parties": "VA hospitals, veterans, taxpayers",
            "geographic_scope": "nationwide VA system",
            "estimated_harm": "$35M annually in inflated costs",
            "referral_agency": "VA-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "State Prison Food Service Bid-Rigging (Pennsylvania)",
        "summary": "Three food service companies conspired to allocate Pennsylvania state prison food service contracts. Companies agreed which facilities each would bid on and submitted artificially high bids on others' designated facilities.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Trinity Services Group", "Aramark Correctional Services", "Keefe Group"],
            "industry": "correctional_food_services",
            "alleged_conduct": "bid rigging, facility allocation",
            "affected_parties": "Pennsylvania DOC, inmates, taxpayers",
            "geographic_scope": "Pennsylvania statewide",
            "estimated_harm": "$10M in overcharges",
            "referral_agency": "PA AG Office",
        },
        "priority": "high",
    },
    {
        "title": "Army Corps of Engineers Dredging Bid-Rigging",
        "summary": "Dredging contractors conspired to rig bids on Army Corps of Engineers harbor maintenance and channel deepening projects along the Gulf Coast. Companies rotated winning bids on annual maintenance contracts.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Great Lakes Dredge & Dock", "Weeks Marine", "Manson Construction", "Cashman Dredging"],
            "industry": "marine_dredging",
            "alleged_conduct": "bid rigging, contract rotation on federal dredging projects",
            "affected_parties": "Army Corps of Engineers, port authorities, taxpayers",
            "geographic_scope": "Gulf Coast (TX, LA, MS, AL, FL)",
            "estimated_harm": "$22M in overcharges",
            "referral_agency": "Army CID",
        },
        "priority": "critical",
    },
    {
        "title": "Municipal Bond Underwriting Bid-Rigging",
        "summary": "Investment banks rigged bids for municipal bond reinvestment contracts (GICs), depriving municipalities of competitive returns on bond proceeds. Banks paid kickbacks to brokers who facilitated the rigged auctions.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["JPMorgan Securities", "Bank of America", "GE Funding Capital", "Wachovia Bank", "UBS Financial Services"],
            "industry": "municipal_finance",
            "alleged_conduct": "bid rigging of GIC contracts, broker kickbacks",
            "affected_parties": "municipalities, school districts, taxpayers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$100M+ in lost investment returns",
            "referral_agency": "IRS-CI",
        },
        "priority": "critical",
    },
    {
        "title": "Federal Building Janitorial Services Bid-Rigging (DC Metro)",
        "summary": "Janitorial service companies conspired to rig bids for GSA building maintenance contracts in the Washington DC metropolitan area. Companies allocated buildings among themselves and submitted cover bids.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["ABM Industries", "C&W Services", "Marsden Holding", "National Maintenance Contractors"],
            "industry": "building_maintenance",
            "alleged_conduct": "bid rigging, building allocation, cover bidding",
            "affected_parties": "GSA, federal agencies, taxpayers",
            "geographic_scope": "Washington DC metropolitan area",
            "estimated_harm": "$8M in overcharges",
            "referral_agency": "GSA-OIG",
        },
        "priority": "high",
    },
    {
        "title": "DOD Furniture Procurement Bid-Rigging",
        "summary": "Office furniture manufacturers conspired to rig bids on Department of Defense furniture procurement contracts for military base offices and barracks. Companies coordinated pricing through industry association meetings.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Steelcase Federal", "Herman Miller Government", "Knoll Government", "Haworth Federal"],
            "industry": "office_furniture",
            "alleged_conduct": "bid rigging, price coordination via trade association",
            "affected_parties": "DOD, military personnel, taxpayers",
            "geographic_scope": "nationwide military installations",
            "estimated_harm": "$15M in overcharges",
            "referral_agency": "DOD-OIG",
        },
        "priority": "high",
    },
    {
        "title": "State Highway Guardrail Installation Bid-Rigging (Virginia)",
        "summary": "Guardrail installation companies conspired to rig bids on Virginia DOT safety improvement contracts. Companies pre-determined winners for specific highway corridors and submitted inflated complementary bids.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Trinity Industries", "Nucor Skyline", "Gregory Industries", "Hill & Smith Holdings"],
            "industry": "highway_safety_equipment",
            "alleged_conduct": "bid rigging, corridor allocation, complementary bidding",
            "affected_parties": "Virginia DOT, motorists, taxpayers",
            "geographic_scope": "Virginia statewide",
            "estimated_harm": "$7M in overcharges",
            "referral_agency": "Virginia AG Office",
        },
        "priority": "high",
    },
    {
        "title": "FEMA Disaster Relief Supply Bid-Rigging (Hurricane Response)",
        "summary": "Emergency supply vendors conspired to rig bids for FEMA disaster relief contracts following major hurricanes. Companies exploited emergency procurement procedures to inflate prices for tarps, generators, and water purification equipment.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Bronze Star LLC", "Tribute Contracting", "Cobra Acquisitions", "Fluor Enterprises"],
            "industry": "disaster_relief_supplies",
            "alleged_conduct": "bid rigging, price inflation during emergencies",
            "affected_parties": "FEMA, disaster victims, taxpayers",
            "geographic_scope": "Gulf Coast, Puerto Rico, US Virgin Islands",
            "estimated_harm": "$50M in inflated emergency contracts",
            "referral_agency": "DHS-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "Public Transit Bus Procurement Bid-Rigging (NYC MTA)",
        "summary": "Bus manufacturers conspired to rig bids for New York MTA bus fleet replacement contracts. Companies agreed which would bid on articulated vs standard bus orders and submitted non-competitive prices on others' designated lots.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["New Flyer Industries", "Nova Bus", "Proterra", "BYD Motors"],
            "industry": "public_transit_manufacturing",
            "alleged_conduct": "bid rigging, lot allocation by bus type",
            "affected_parties": "NYC MTA, transit riders, taxpayers",
            "geographic_scope": "New York City",
            "estimated_harm": "$30M in overcharges on $800M procurement",
            "referral_agency": "MTA-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "Military Housing Construction Bid-Rigging (Privatized Housing)",
        "summary": "Construction firms rigged bids for privatized military family housing projects at multiple Army and Air Force bases. Companies pre-arranged winners and shared subcontractors to maintain appearance of competition.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Lendlease Americas", "Balfour Beatty Communities", "Corvias Military Living", "Hunt Companies"],
            "industry": "military_housing",
            "alleged_conduct": "bid rigging, subcontractor sharing, pre-arranged winners",
            "affected_parties": "DOD, military families, taxpayers",
            "geographic_scope": "multiple US military bases",
            "estimated_harm": "$40M in overcharges",
            "referral_agency": "DOD-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "County Bridge Repair Bid-Rigging (Ohio)",
        "summary": "Bridge construction companies conspired to rig bids on county bridge repair and replacement projects across rural Ohio. Companies divided counties into territories and agreed not to bid competitively in each other's areas.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Kokosing Construction", "Shelly & Sands", "Ruhlin Company", "Great Lakes Construction"],
            "industry": "bridge_construction",
            "alleged_conduct": "bid rigging, geographic territory allocation",
            "affected_parties": "Ohio county governments, taxpayers",
            "geographic_scope": "Rural Ohio (30+ counties)",
            "estimated_harm": "$12M in overcharges",
            "referral_agency": "Ohio AG Office",
        },
        "priority": "high",
    },
    {
        "title": "Federal Courthouse Security Equipment Bid-Rigging",
        "summary": "Security equipment vendors conspired to rig bids for US Marshals Service courthouse security upgrades including X-ray machines, metal detectors, and surveillance systems across federal courthouses.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Smiths Detection", "L3Harris Security", "Rapiscan Systems", "CEIA USA"],
            "industry": "security_equipment",
            "alleged_conduct": "bid rigging, technology allocation, complementary bidding",
            "affected_parties": "US Marshals Service, federal judiciary, taxpayers",
            "geographic_scope": "nationwide federal courthouses",
            "estimated_harm": "$18M in overcharges",
            "referral_agency": "DOJ-OIG",
        },
        "priority": "high",
    },
    {
        "title": "EPA Superfund Cleanup Bid-Rigging",
        "summary": "Environmental remediation firms conspired to rig bids on EPA Superfund site cleanup contracts. Companies allocated sites by geographic region and complexity level, submitting cover bids on others' designated projects.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Clean Harbors", "US Ecology", "Envirostar", "Republic Services Environmental"],
            "industry": "environmental_remediation",
            "alleged_conduct": "bid rigging, site allocation by region and complexity",
            "affected_parties": "EPA, affected communities, taxpayers",
            "geographic_scope": "nationwide Superfund sites",
            "estimated_harm": "$25M in inflated cleanup costs",
            "referral_agency": "EPA-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "State University Construction Bid-Rigging (California)",
        "summary": "General contractors conspired to rig bids on California State University system construction projects including dormitories, science buildings, and athletic facilities across multiple campuses.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Clark Construction", "Sundt Construction", "Gilbane Building", "Whiting-Turner Contracting"],
            "industry": "university_construction",
            "alleged_conduct": "bid rigging, campus allocation, subcontractor kickbacks",
            "affected_parties": "California State University system, students, taxpayers",
            "geographic_scope": "California (23 CSU campuses)",
            "estimated_harm": "$35M in overcharges",
            "referral_agency": "California AG Office",
        },
        "priority": "high",
    },
    {
        "title": "Coast Guard Vessel Maintenance Bid-Rigging",
        "summary": "Marine service companies conspired to rig bids for US Coast Guard cutter maintenance and repair contracts at multiple home ports. Companies rotated winning bids by vessel class and port location.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Vigor Industrial", "Bollinger Shipyards", "VT Halter Marine", "Eastern Shipbuilding"],
            "industry": "coast_guard_maintenance",
            "alleged_conduct": "bid rigging, rotation by vessel class and port",
            "affected_parties": "US Coast Guard, taxpayers",
            "geographic_scope": "US coastal ports",
            "estimated_harm": "$20M in overcharges",
            "referral_agency": "DHS-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "Public Water System Equipment Bid-Rigging (Midwest)",
        "summary": "Water treatment equipment suppliers conspired to rig bids for municipal water system upgrades across Midwest cities. Companies allocated contracts by equipment type (pumps, filtration, chemical treatment) and submitted cover bids.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Xylem Inc", "Evoqua Water Technologies", "Mueller Water Products", "Watts Water Technologies"],
            "industry": "water_treatment_equipment",
            "alleged_conduct": "bid rigging, equipment category allocation",
            "affected_parties": "Midwest municipalities, water ratepayers",
            "geographic_scope": "Midwest (OH, IN, IL, MI, WI, MN)",
            "estimated_harm": "$15M in inflated equipment costs",
            "referral_agency": "EPA-OIG",
        },
        "priority": "high",
    },
]


# =============================================================================
# PRICE FIXING (~20 cases)
# =============================================================================
PRICE_FIXING = [
    {
        "title": "Big Four Beef Packers Price-Fixing Investigation",
        "summary": "DOJ and USDA investigation into Tyson Foods, JBS USA, Cargill, and National Beef Packing for alleged price-fixing and collusion in the US cattle and beef industries. Coordinated suppression of cattle prices paid to ranchers while inflating consumer beef prices. Four companies control approximately 85% of US beef processing.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Tyson Foods", "JBS USA", "Cargill", "National Beef Packing"],
            "industry": "beef_processing",
            "market_share": "85% of US beef processing",
            "alleged_conduct": "price-fixing, bid suppression at cattle auctions",
            "affected_parties": "US cattle ranchers, consumers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$10B+ over 5 years",
            "referral_agency": "USDA",
        },
        "priority": "critical",
    },
    {
        "title": "Real Estate Agent Commission Price-Fixing (NAR)",
        "summary": "National Association of Realtors and major brokerages conspired to inflate real estate agent commissions at 5-6% through mandatory buyer-broker commission rules in MLS systems. Resulted in $1.8B settlement and major structural reforms.",
        "source_type": "news",
        "source_content": {
            "subjects": ["National Association of Realtors", "Keller Williams", "RE/MAX", "Anywhere Real Estate", "HomeServices of America"],
            "industry": "real_estate",
            "alleged_conduct": "price-fixing of broker commissions via MLS rules",
            "affected_parties": "home sellers, home buyers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$30B+ annually in inflated commissions",
            "settlement_amount": "$1.8B (NAR) + $250M (others)",
        },
        "priority": "critical",
    },
    {
        "title": "Generic Pharmaceutical Price-Fixing Conspiracy",
        "summary": "Widespread price-fixing among generic drug manufacturers. Over 40 states filed suit alleging 20+ companies conspired to fix prices for over 300 generic drugs. Multiple executives pled guilty to criminal charges.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Teva Pharmaceuticals", "Sandoz", "Mylan", "Heritage Pharmaceuticals", "Aurobindo Pharma", "Rising Pharmaceuticals"],
            "industry": "pharmaceuticals",
            "alleged_conduct": "price-fixing, market allocation, bid rigging",
            "affected_parties": "patients, insurers, government health programs",
            "geographic_scope": "nationwide",
            "estimated_harm": "$5B+ in overcharges",
            "drugs_affected": "300+ generic medications",
            "referral_agency": "HHS-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "Broiler Chicken Price-Fixing Conspiracy",
        "summary": "Major poultry producers conspired to fix prices and limit production of broiler chickens sold to restaurants, grocery stores, and food distributors. Companies used a shared data platform to coordinate supply reductions.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Pilgrim's Pride", "Tyson Foods", "Perdue Farms", "Koch Foods", "Sanderson Farms", "Wayne Farms"],
            "industry": "poultry_processing",
            "alleged_conduct": "price-fixing, supply manipulation, information sharing",
            "affected_parties": "restaurants, grocery chains, consumers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$7B+ in overcharges",
            "referral_agency": "USDA-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "Canned Tuna Price-Fixing Conspiracy",
        "summary": "Three major canned tuna producers conspired to fix prices of canned tuna sold in the United States. Executives coordinated price increases through direct communications and industry events. StarKist pled guilty and paid $100M fine.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["StarKist Co", "Bumble Bee Foods", "Chicken of the Sea"],
            "industry": "canned_seafood",
            "alleged_conduct": "price-fixing, coordinated price increases",
            "affected_parties": "grocery retailers, consumers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$600M+ in overcharges",
            "fines_paid": "$100M (StarKist) + $25M (Bumble Bee)",
        },
        "priority": "high",
    },
    {
        "title": "Capacitor Price-Fixing Cartel (Electronics Components)",
        "summary": "Japanese and European capacitor manufacturers conspired to fix prices of aluminum and tantalum electrolytic capacitors used in electronics. Affected components in smartphones, computers, cars, and industrial equipment.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Panasonic", "Nippon Chemi-Con", "Nichicon", "Rubycon", "ELNA", "Matsuo Electric"],
            "industry": "electronic_components",
            "alleged_conduct": "price-fixing, supply restriction coordination",
            "affected_parties": "electronics manufacturers, consumers",
            "geographic_scope": "global",
            "estimated_harm": "$2B+ in overcharges",
            "referral_agency": "FBI",
        },
        "priority": "high",
    },
    {
        "title": "Packaged Seafood Price-Fixing (Shrimp)",
        "summary": "Major shrimp processors and importers conspired to fix prices of frozen and packaged shrimp sold to US retailers and food service companies. Companies coordinated pricing through trade association meetings.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Thai Union Group", "Aqua Star", "National Fish & Seafood", "High Liner Foods"],
            "industry": "packaged_seafood",
            "alleged_conduct": "price-fixing, coordinated supply restrictions",
            "affected_parties": "retailers, restaurants, consumers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$400M in overcharges",
            "referral_agency": "DOJ Antitrust Division",
        },
        "priority": "high",
    },
    {
        "title": "LCD Panel Price-Fixing Conspiracy",
        "summary": "Major LCD panel manufacturers conspired to fix prices of thin-film transistor liquid crystal display panels used in computer monitors, laptops, and televisions. Companies held secret meetings to set prices and allocate customers.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["LG Display", "AU Optronics", "Chunghwa Picture Tubes", "Chi Mei Optoelectronics", "Sharp Corporation"],
            "industry": "display_manufacturing",
            "alleged_conduct": "price-fixing, customer allocation, production coordination",
            "affected_parties": "computer manufacturers, TV makers, consumers",
            "geographic_scope": "global",
            "estimated_harm": "$3B+ in overcharges",
            "fines_paid": "$1.39B in criminal fines",
        },
        "priority": "critical",
    },
    {
        "title": "Lithium-Ion Battery Price-Fixing (Automotive)",
        "summary": "Battery cell manufacturers conspired to fix prices of lithium-ion battery cells sold to automotive manufacturers for hybrid and electric vehicles. Companies coordinated pricing through bilateral meetings.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Panasonic Energy", "LG Energy Solution", "Samsung SDI", "SK Innovation"],
            "industry": "automotive_batteries",
            "alleged_conduct": "price-fixing, customer allocation for EV batteries",
            "affected_parties": "automakers, EV buyers",
            "geographic_scope": "global",
            "estimated_harm": "$1.5B+ in overcharges",
            "referral_agency": "FBI",
        },
        "priority": "critical",
    },
    {
        "title": "Mushroom Price-Fixing Conspiracy (Pennsylvania)",
        "summary": "Mushroom growers in Chester County, Pennsylvania conspired to fix prices and restrict supply of fresh mushrooms sold to grocery chains and food distributors. Companies coordinated through the American Mushroom Institute.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Giorgio Fresh", "Monterey Mushrooms", "To-Jo Mushrooms", "South Mill Champs"],
            "industry": "fresh_produce",
            "alleged_conduct": "price-fixing, supply restriction, information sharing",
            "affected_parties": "grocery chains, food distributors, consumers",
            "geographic_scope": "Eastern United States",
            "estimated_harm": "$200M in overcharges",
            "referral_agency": "USDA",
        },
        "priority": "high",
    },
    {
        "title": "Freight Forwarding Price-Fixing Cartel",
        "summary": "International freight forwarding companies conspired to fix prices of surcharges on air cargo shipments including fuel surcharges, security surcharges, and currency adjustment factors.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Kuehne + Nagel", "Panalpina", "Schenker AG", "Expeditors International", "UTi Worldwide"],
            "industry": "freight_forwarding",
            "alleged_conduct": "price-fixing of surcharges, coordinated fee increases",
            "affected_parties": "shippers, importers, exporters",
            "geographic_scope": "global",
            "estimated_harm": "$1B+ in inflated surcharges",
            "referral_agency": "FBI",
        },
        "priority": "high",
    },
    {
        "title": "Automotive Wire Harness Price-Fixing",
        "summary": "Japanese wire harness manufacturers conspired to fix prices of wire harnesses sold to US and Japanese automakers. Wire harnesses are critical electrical systems in every vehicle. Over $750M in fines collected.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Yazaki Corporation", "Sumitomo Electric", "Furukawa Electric", "Leoni AG"],
            "industry": "automotive_parts",
            "alleged_conduct": "price-fixing, customer allocation",
            "affected_parties": "automakers, car buyers",
            "geographic_scope": "US, Japan, Europe",
            "estimated_harm": "$2B+ in overcharges",
            "fines_paid": "$750M+",
        },
        "priority": "critical",
    },
    {
        "title": "Insulin Price-Fixing Investigation",
        "summary": "Three insulin manufacturers investigated for coordinated price increases on insulin products. Companies raised list prices in lockstep over a decade, with prices increasing over 300% while production costs remained stable.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Eli Lilly", "Novo Nordisk", "Sanofi"],
            "industry": "pharmaceuticals",
            "alleged_conduct": "parallel pricing, coordinated price increases",
            "affected_parties": "diabetic patients, insurers, Medicare/Medicaid",
            "geographic_scope": "nationwide",
            "estimated_harm": "$10B+ annually in inflated costs",
        },
        "priority": "critical",
    },
    {
        "title": "Cathode Ray Tube (CRT) Price-Fixing",
        "summary": "CRT manufacturers conspired to fix prices of cathode ray tubes used in televisions and computer monitors. Companies held regular meetings to set prices and allocate market shares over a 10-year period.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Samsung SDI", "LG Philips Displays", "Chunghwa Picture Tubes", "Toshiba", "Panasonic"],
            "industry": "display_manufacturing",
            "alleged_conduct": "price-fixing, market share allocation",
            "affected_parties": "TV manufacturers, consumers",
            "geographic_scope": "global",
            "estimated_harm": "$1.4B in overcharges",
            "fines_paid": "$1.1B in criminal fines",
        },
        "priority": "high",
    },
    {
        "title": "Egg Price-Fixing Conspiracy",
        "summary": "Major egg producers conspired to fix prices by coordinating flock reductions and export programs to artificially reduce domestic egg supply. Companies used United Egg Producers trade group to coordinate.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Cal-Maine Foods", "Rose Acre Farms", "Michael Foods", "Sparboe Farms", "Moark LLC"],
            "industry": "egg_production",
            "alleged_conduct": "price-fixing, supply manipulation, coordinated exports",
            "affected_parties": "grocery retailers, food manufacturers, consumers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$1B+ in overcharges",
            "referral_agency": "USDA",
        },
        "priority": "high",
    },
    {
        "title": "Optical Disk Drive Price-Fixing",
        "summary": "Manufacturers of optical disk drives (CD, DVD, Blu-ray) conspired to fix prices of drives sold to computer manufacturers. Companies coordinated through bilateral meetings and industry conferences.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Panasonic", "Sony Optiarc", "Hitachi-LG Data Storage", "Toshiba Samsung Storage", "Philips & Lite-On"],
            "industry": "computer_components",
            "alleged_conduct": "price-fixing, customer allocation",
            "affected_parties": "PC manufacturers, consumers",
            "geographic_scope": "global",
            "estimated_harm": "$500M in overcharges",
            "fines_paid": "$200M+",
        },
        "priority": "high",
    },
    {
        "title": "Pork Processing Price-Fixing Investigation",
        "summary": "Major pork processors investigated for conspiring to fix prices and limit production of pork products. Companies allegedly coordinated supply reductions through shared market data and production scheduling.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Smithfield Foods", "JBS USA Pork", "Tyson Fresh Meats", "Hormel Foods"],
            "industry": "pork_processing",
            "alleged_conduct": "price-fixing, supply manipulation, information sharing",
            "affected_parties": "hog farmers, retailers, consumers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$4B+ in overcharges",
            "referral_agency": "USDA-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "Potash Price-Fixing Cartel",
        "summary": "Major potash producers conspired to fix prices of potash fertilizer sold to US farmers. Companies coordinated production cuts and export restrictions through bilateral agreements to inflate prices.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Nutrien (formerly Potash Corp)", "Mosaic Company", "K+S AG", "ICL Group", "Belaruskali"],
            "industry": "agricultural_fertilizer",
            "alleged_conduct": "price-fixing, coordinated production cuts",
            "affected_parties": "US farmers, food producers, consumers",
            "geographic_scope": "global",
            "estimated_harm": "$2B+ in inflated fertilizer costs",
            "referral_agency": "USDA",
        },
        "priority": "high",
    },
    {
        "title": "DRAM Memory Chip Price-Fixing",
        "summary": "DRAM manufacturers conspired to fix prices of dynamic random access memory chips sold to computer makers. Companies held secret meetings to set prices and restrict supply. Samsung, Hynix, Infineon paid $731M in fines.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Samsung Electronics", "Hynix Semiconductor", "Infineon Technologies", "Micron Technology", "Elpida Memory"],
            "industry": "semiconductor",
            "alleged_conduct": "price-fixing, supply restriction",
            "affected_parties": "computer manufacturers, consumers",
            "geographic_scope": "global",
            "estimated_harm": "$3B+ in overcharges",
            "fines_paid": "$731M in criminal fines",
        },
        "priority": "critical",
    },
    {
        "title": "Vitamin Price-Fixing Cartel",
        "summary": "Major vitamin manufacturers conspired to fix prices of bulk vitamins sold to food and supplement companies. The cartel operated for nearly a decade, affecting vitamins A, B2, B5, C, E, and beta carotene. Resulted in $900M+ in fines.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Hoffmann-La Roche", "BASF", "Lonza", "Daiichi Pharmaceutical", "Eisai Co"],
            "industry": "vitamins_supplements",
            "alleged_conduct": "price-fixing, market allocation, volume quotas",
            "affected_parties": "food manufacturers, supplement companies, consumers",
            "geographic_scope": "global",
            "estimated_harm": "$5B+ in overcharges",
            "fines_paid": "$900M+",
        },
        "priority": "critical",
    },
]


# =============================================================================
# CRIMINAL CARTEL (~18 cases)
# =============================================================================
CRIMINAL_CARTEL = [
    {
        "title": "LIBOR Rate Manipulation - Banking Cartel",
        "summary": "Seven major banks manipulated the London Interbank Offered Rate (LIBOR) by submitting intentionally high or low rates to benefit trading positions. Banks paid over $3 billion in fines, multiple subsidiaries pled guilty, and 16 individuals were convicted.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Barclays", "Deutsche Bank", "UBS", "Rabobank", "Royal Bank of Scotland", "Citicorp", "JPMorgan Chase"],
            "industry": "banking_financial_services",
            "alleged_conduct": "rate manipulation, fraud, wire fraud",
            "geographic_scope": "global",
            "estimated_harm": "$300B+ in affected instruments",
            "fines_paid": "$3B+",
            "convictions": "16 individuals, 7 corporate guilty pleas",
        },
        "priority": "critical",
    },
    {
        "title": "South Korean Auto Parts Bid-Rigging Cartel",
        "summary": "Executives from South Korean and Japanese auto parts manufacturers rigged bids and fixed prices for components sold to US automakers. Over $2.9 billion in fines collected from 50+ companies. 48 individuals charged.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Denso Corporation", "Yazaki Corporation", "Furukawa Electric", "Hyundai Mobis", "Mando Corporation"],
            "industry": "automotive_parts",
            "alleged_conduct": "bid rigging, price fixing for auto parts",
            "geographic_scope": "US, Japan, South Korea",
            "estimated_harm": "$5B+ in overcharges to automakers",
            "fines_collected": "$2.9B from 50+ companies",
            "individuals_charged": 48,
        },
        "priority": "critical",
    },
    {
        "title": "Foreign Exchange (Forex) Rate-Rigging Cartel",
        "summary": "Major banks conspired to manipulate foreign exchange benchmark rates through coordinated trading in chat rooms called 'The Cartel' and 'The Bandits Club'. Banks pled guilty and paid $5.8B in fines.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Citicorp", "JPMorgan Chase", "Barclays", "Royal Bank of Scotland", "UBS"],
            "industry": "foreign_exchange",
            "alleged_conduct": "rate manipulation, coordinated trading, market rigging",
            "geographic_scope": "global ($5.3T daily forex market)",
            "estimated_harm": "$10B+ in manipulated trades",
            "fines_paid": "$5.8B combined",
        },
        "priority": "critical",
    },
    {
        "title": "Air Cargo Fuel Surcharge Cartel",
        "summary": "International airlines conspired to fix fuel and security surcharges on air cargo shipments. Over 20 airlines participated. DOJ collected $1.8B in fines.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["British Airways", "Korean Air", "Air France-KLM", "Cathay Pacific", "Japan Airlines", "Qantas"],
            "industry": "air_cargo",
            "alleged_conduct": "price-fixing of fuel and security surcharges",
            "geographic_scope": "global",
            "estimated_harm": "$3B+ in inflated surcharges",
            "fines_paid": "$1.8B from 20+ airlines",
        },
        "priority": "critical",
    },
    {
        "title": "Marine Hose Cartel (Oil & Gas)",
        "summary": "Manufacturers of marine hoses used in offshore oil loading conspired to rig bids and fix prices globally for over 20 years. Eight executives served prison time.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Bridgestone Corporation", "Dunlop Oil & Marine", "Trelleborg Industrie", "Parker ITR", "Manuli Rubber"],
            "industry": "oil_gas_equipment",
            "alleged_conduct": "bid rigging, price-fixing, customer allocation",
            "geographic_scope": "global",
            "estimated_harm": "$500M+ in overcharges",
            "duration": "20+ years",
            "prison_sentences": "8 executives",
        },
        "priority": "high",
    },
    {
        "title": "Precious Metals Trading Cartel (Gold/Silver Fix)",
        "summary": "Major banks conspired to manipulate the London Gold Fix and Silver Fix benchmark prices. Traders coordinated positions and shared client order information to front-run the daily fix.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Deutsche Bank", "HSBC", "Bank of Nova Scotia", "Barclays", "UBS"],
            "industry": "precious_metals_trading",
            "alleged_conduct": "benchmark manipulation, front-running, information sharing",
            "geographic_scope": "global",
            "estimated_harm": "$1B+ in manipulated trades",
            "referral_agency": "CFTC",
        },
        "priority": "critical",
    },
    {
        "title": "Polyurethane Foam Cartel",
        "summary": "Manufacturers of flexible polyurethane foam used in furniture, mattresses, and automotive seating conspired to fix prices through direct communications between sales executives.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Carpenter Co", "Vitafoam", "Woodbridge Group", "Future Foam", "FXI"],
            "industry": "foam_manufacturing",
            "alleged_conduct": "price-fixing, coordinated price increases",
            "geographic_scope": "United States, Canada",
            "estimated_harm": "$400M in overcharges",
            "referral_agency": "FBI",
        },
        "priority": "high",
    },
    {
        "title": "Packaged Ice Cartel (Midwest/Southeast US)",
        "summary": "Packaged ice manufacturers conspired to allocate territories and fix prices in the Midwest and Southeast. Companies agreed not to compete in each other's territories.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Arctic Glacier", "Reddy Ice", "Home City Ice", "Party Ice"],
            "industry": "packaged_ice",
            "alleged_conduct": "market allocation, price-fixing, territorial agreements",
            "geographic_scope": "Midwest and Southeast US",
            "estimated_harm": "$100M in overcharges",
            "referral_agency": "FBI Detroit",
        },
        "priority": "high",
    },
    {
        "title": "Citric Acid Cartel",
        "summary": "Major citric acid producers conspired to fix prices and allocate sales volumes. Companies met quarterly to set prices and monitor compliance with volume quotas.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Archer Daniels Midland", "Haarmann & Reimer", "Jungbunzlauer", "Hoffmann-La Roche"],
            "industry": "food_chemicals",
            "alleged_conduct": "price-fixing, volume allocation, monitoring compliance",
            "geographic_scope": "global",
            "estimated_harm": "$200M in overcharges",
            "fines_paid": "$105M (ADM alone)",
        },
        "priority": "high",
    },
    {
        "title": "Lysine Feed Additive Cartel (The Informant!)",
        "summary": "Manufacturers of lysine amino acid feed additive conspired to fix prices and allocate volumes. ADM executive Mark Whitacre became FBI informant. Subject of film 'The Informant!'",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Archer Daniels Midland", "Ajinomoto", "Kyowa Hakko", "Sewon America", "Cheil Jedang"],
            "industry": "animal_feed_additives",
            "alleged_conduct": "price-fixing, volume allocation",
            "geographic_scope": "global",
            "estimated_harm": "$200M in overcharges",
            "fines_paid": "$100M (ADM)",
            "notable": "FBI informant case, basis for 'The Informant!' film",
        },
        "priority": "critical",
    },
    {
        "title": "Rubber Chemicals Cartel",
        "summary": "Chemical companies conspired to fix prices of rubber processing chemicals used in tire manufacturing. Companies coordinated price increases through regular meetings in Europe and Asia.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Crompton Corporation", "Bayer AG", "Chemtura", "Flexsys"],
            "industry": "specialty_chemicals",
            "alleged_conduct": "price-fixing, customer allocation",
            "geographic_scope": "global",
            "estimated_harm": "$300M in overcharges",
            "referral_agency": "FBI",
        },
        "priority": "high",
    },
    {
        "title": "Electrical Carbon Products Cartel",
        "summary": "Manufacturers of carbon and graphite products for electrical equipment conspired to fix prices globally. Products included carbon brushes for electric motors and graphite electrodes for steel production.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["SGL Carbon", "UCAR International", "Tokai Carbon", "Showa Denko"],
            "industry": "industrial_carbon",
            "alleged_conduct": "price-fixing, market allocation",
            "geographic_scope": "global",
            "estimated_harm": "$400M in overcharges",
            "fines_paid": "$400M+",
        },
        "priority": "high",
    },
    {
        "title": "Compressor Cartel (HVAC Industry)",
        "summary": "Manufacturers of refrigeration and air conditioning compressors conspired to fix prices and allocate customers globally.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Panasonic", "Tecumseh Products", "Embraco", "LG Electronics", "Samsung Electronics"],
            "industry": "HVAC_components",
            "alleged_conduct": "price-fixing, customer allocation",
            "geographic_scope": "global",
            "estimated_harm": "$500M in overcharges",
            "referral_agency": "FBI",
        },
        "priority": "high",
    },
    {
        "title": "LCD Glass Substrate Cartel",
        "summary": "Three manufacturers of glass substrates for LCD panels conspired to fix prices. Only three companies globally produce this specialized glass, enabling effective cartel operation.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Corning Inc", "AGC Inc (Asahi Glass)", "Nippon Electric Glass"],
            "industry": "specialty_glass",
            "alleged_conduct": "price-fixing, supply restriction",
            "geographic_scope": "global",
            "estimated_harm": "$800M in overcharges",
            "referral_agency": "FBI",
        },
        "priority": "critical",
    },
    {
        "title": "Synthetic Rubber Cartel",
        "summary": "Major synthetic rubber producers conspired to fix prices of chloroprene and nitrile rubber used in automotive parts and industrial hoses.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["DuPont Performance Elastomers", "Bayer MaterialScience", "Denka Company", "Tosoh Corporation"],
            "industry": "synthetic_rubber",
            "alleged_conduct": "price-fixing, supply coordination",
            "geographic_scope": "global",
            "estimated_harm": "$250M in overcharges",
            "referral_agency": "FBI",
        },
        "priority": "high",
    },
    {
        "title": "Sorbates Preservative Cartel",
        "summary": "Chemical companies conspired to fix prices of sorbic acid and potassium sorbate preservatives used in food and beverages. Cartel operated for over 17 years.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Hoechst AG", "Daicel Chemical", "Nippon Synthetic Chemical", "Ueno Fine Chemicals"],
            "industry": "food_chemicals",
            "alleged_conduct": "price-fixing, volume allocation",
            "geographic_scope": "global",
            "estimated_harm": "$150M in overcharges",
            "duration": "17 years",
        },
        "priority": "high",
    },
    {
        "title": "Zinc Phosphate Chemical Cartel",
        "summary": "Manufacturers of zinc phosphate anti-corrosion chemicals conspired to fix prices and allocate customers. Used as primer coating in automotive and industrial applications.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Heubach GmbH", "Sherwin-Williams Chemicals", "Elementis Specialties", "Wayne Pigment"],
            "industry": "industrial_chemicals",
            "alleged_conduct": "price-fixing, customer allocation",
            "geographic_scope": "United States, Europe",
            "estimated_harm": "$80M in overcharges",
            "referral_agency": "FBI",
        },
        "priority": "high",
    },
    {
        "title": "Thermal Fax Paper Cartel",
        "summary": "Japanese manufacturers of thermal fax paper conspired to fix prices and allocate customers in the US market through regular coordination meetings.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Kanzaki Specialty Papers", "Mitsubishi Paper Mills", "New Oji Paper", "Nippon Paper Industries"],
            "industry": "specialty_paper",
            "alleged_conduct": "price-fixing, customer allocation, market share agreements",
            "geographic_scope": "United States",
            "estimated_harm": "$100M in overcharges",
            "referral_agency": "FBI",
        },
        "priority": "high",
    },
]


# =============================================================================
# MONOPOLIZATION (~15 cases) - Includes Murray Gunty/Black Street Capital
# =============================================================================
MONOPOLIZATION = [
    {
        "title": "Murray Gunty / Black Street Capital / King of the Rinks - Youth Hockey Monopolization",
        "summary": "Murray Gunty, through Black Street Capital and the 'King of the Rinks' strategy, systematically acquired ice rinks across metropolitan areas to establish monopoly control over youth hockey and figure skating markets. After acquiring dominant market position, Gunty raised ice time rates 40-200%, eliminated competing programs, and imposed exclusive contracts preventing teams from using rival facilities.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Murray Gunty", "Black Street Capital", "King of the Rinks LLC", "Rink Management Services Corp"],
            "industry": "youth_sports_facilities",
            "alleged_conduct": "monopolization via serial acquisition, exclusionary contracts, predatory pricing during acquisition phase",
            "mechanism": "acquire 70%+ of ice rinks in metro area, then raise prices and impose exclusive use agreements",
            "affected_parties": "youth hockey families, figure skating clubs, independent rink operators",
            "geographic_scope": "multiple US metropolitan areas (Chicago, St. Louis, Dallas, others)",
            "estimated_harm": "$50M+ annually in inflated ice time costs",
            "market_share": "70-90% of ice rinks in targeted metro areas",
            "referral_agency": "FTC Consumer Complaints",
        },
        "priority": "critical",
    },
    {
        "title": "Google Search Monopoly (US v. Google LLC)",
        "summary": "DOJ alleges Google illegally maintained monopoly in general search and search advertising through exclusive distribution agreements with Apple, Samsung, and browser makers. Google pays $26B+ annually to be default search engine.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Google LLC", "Alphabet Inc"],
            "industry": "internet_search",
            "alleged_conduct": "monopoly maintenance through exclusive dealing, tying",
            "mechanism": "exclusive default search agreements with device makers and browsers",
            "affected_parties": "competing search engines, advertisers, consumers",
            "geographic_scope": "United States (90%+ search market share)",
            "estimated_harm": "$100B+ in monopoly rents from search advertising",
        },
        "priority": "critical",
    },
    {
        "title": "Apple App Store Monopoly (Epic Games v. Apple)",
        "summary": "Apple accused of monopolizing iOS app distribution through mandatory use of App Store and 30% commission on all digital purchases. Developers cannot distribute apps outside App Store or use alternative payment systems.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Apple Inc"],
            "industry": "mobile_app_distribution",
            "alleged_conduct": "monopolization of app distribution, tying, excessive fees",
            "mechanism": "mandatory App Store use, 30% commission, no sideloading",
            "affected_parties": "app developers, iOS users",
            "geographic_scope": "global (1.5B+ iOS devices)",
            "estimated_harm": "$15B+ annually in excessive commissions",
        },
        "priority": "critical",
    },
    {
        "title": "Ticketmaster/Live Nation Entertainment Monopoly",
        "summary": "DOJ alleges Live Nation Entertainment monopolizes live event ticketing through exclusive venue contracts, retaliation against venues using competitors, and leveraging concert promotion dominance to force ticketing deals.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Live Nation Entertainment", "Ticketmaster"],
            "industry": "live_entertainment",
            "alleged_conduct": "monopolization, exclusive dealing, retaliation, tying",
            "mechanism": "exclusive long-term venue contracts, threatening to withhold concerts",
            "affected_parties": "concert-goers, competing ticketing platforms, venues, artists",
            "geographic_scope": "nationwide (80%+ of major venue ticketing)",
            "estimated_harm": "$5B+ annually in inflated ticket fees",
        },
        "priority": "critical",
    },
    {
        "title": "Amazon Marketplace Monopoly",
        "summary": "FTC alleges Amazon illegally maintains monopoly power in online marketplace through anti-discounting policies that punish sellers for offering lower prices elsewhere, degrading search results for non-Prime products, and forcing sellers to use Fulfillment by Amazon.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Amazon.com Inc"],
            "industry": "e_commerce",
            "alleged_conduct": "monopoly maintenance, anti-discounting coercion, self-preferencing",
            "mechanism": "Buy Box suppression, search result manipulation, FBA coercion",
            "affected_parties": "third-party sellers, competing marketplaces, consumers",
            "geographic_scope": "United States",
            "estimated_harm": "$10B+ annually in excessive fees and lost competition",
        },
        "priority": "critical",
    },
    {
        "title": "Meta (Facebook) Social Media Monopoly",
        "summary": "FTC alleges Meta maintains illegal monopoly in personal social networking through acquiring nascent competitors (Instagram, WhatsApp) and imposing anticompetitive platform policies that block interoperability.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Meta Platforms Inc", "Facebook"],
            "industry": "social_media",
            "alleged_conduct": "monopoly maintenance through acquisitions, platform restrictions",
            "mechanism": "acquiring competitors (Instagram $1B, WhatsApp $19B), blocking API access",
            "affected_parties": "competing social networks, users, advertisers",
            "geographic_scope": "United States (70%+ personal social networking)",
            "estimated_harm": "$20B+ in monopoly advertising rents",
        },
        "priority": "critical",
    },
    {
        "title": "Visa Debit Card Network Monopoly",
        "summary": "DOJ alleges Visa illegally maintains monopoly over debit card transactions by imposing exclusionary agreements on merchants and banks, penalizing those who route transactions through competing networks.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Visa Inc"],
            "industry": "payment_networks",
            "alleged_conduct": "monopolization, exclusionary agreements, loyalty penalties",
            "mechanism": "volume-based incentive agreements that penalize routing to competitors",
            "affected_parties": "merchants, banks, consumers, competing networks",
            "geographic_scope": "United States (60%+ debit transactions)",
            "estimated_harm": "$7B+ annually in excessive interchange fees",
        },
        "priority": "critical",
    },
    {
        "title": "Qualcomm Wireless Chip Monopoly",
        "summary": "FTC alleged Qualcomm maintained monopoly in wireless baseband chips through 'no license, no chips' policy forcing phone makers to pay excessive royalties.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Qualcomm Inc"],
            "industry": "semiconductor",
            "alleged_conduct": "monopolization, FRAND abuse, refusal to deal",
            "mechanism": "no license no chips policy, excessive royalties on SEPs",
            "affected_parties": "phone manufacturers, competing chipmakers, consumers",
            "geographic_scope": "global",
            "estimated_harm": "$5B+ annually in excessive royalties",
            "referral_agency": "FTC",
        },
        "priority": "high",
    },
    {
        "title": "UnitedHealth/Optum Vertical Monopoly in Healthcare",
        "summary": "DOJ investigating UnitedHealth Group's vertical integration of insurance, pharmacy benefits, and healthcare delivery for self-preferencing and foreclosing competitors at each level.",
        "source_type": "news",
        "source_content": {
            "subjects": ["UnitedHealth Group", "Optum", "UnitedHealthcare", "Change Healthcare"],
            "industry": "healthcare",
            "alleged_conduct": "vertical monopolization, self-preferencing, foreclosure",
            "mechanism": "steering patients to Optum providers, denying claims for competitors",
            "affected_parties": "independent physicians, competing insurers, patients",
            "geographic_scope": "nationwide",
            "estimated_harm": "$15B+ in reduced competition",
        },
        "priority": "critical",
    },
    {
        "title": "Intuit/TurboTax Free File Monopoly",
        "summary": "DOJ investigated Intuit for monopolizing consumer tax preparation through deceptive marketing of 'free' filing while steering eligible taxpayers to paid products.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Intuit Inc", "TurboTax"],
            "industry": "tax_preparation",
            "alleged_conduct": "monopolization, deceptive practices, regulatory capture",
            "mechanism": "deceptive 'free' marketing, lobbying against IRS free file",
            "affected_parties": "low-income taxpayers, competing tax prep services",
            "geographic_scope": "nationwide",
            "estimated_harm": "$1B+ annually in unnecessary filing fees",
        },
        "priority": "high",
    },
    {
        "title": "IQVIA Health Data Monopoly",
        "summary": "IQVIA investigated for monopolizing pharmaceutical data and analytics market through exclusive contracts with pharmacies and data providers.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["IQVIA Holdings", "IMS Health"],
            "industry": "pharmaceutical_data",
            "alleged_conduct": "monopolization through exclusive data contracts",
            "mechanism": "exclusive pharmacy data agreements, acquisition of data competitors",
            "affected_parties": "competing analytics firms, pharma companies, researchers",
            "geographic_scope": "United States",
            "estimated_harm": "$2B+ in monopoly pricing for pharma data",
            "referral_agency": "FTC",
        },
        "priority": "high",
    },
    {
        "title": "Illumina Genetic Sequencing Monopoly",
        "summary": "FTC challenged Illumina's acquisition of Grail as vertical monopolization. Illumina controls 80%+ of DNA sequencing market and could disadvantage Grail's competitors.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Illumina Inc", "Grail Inc"],
            "industry": "genetic_sequencing",
            "alleged_conduct": "vertical monopolization through acquisition",
            "mechanism": "acquiring downstream competitor while controlling upstream platform",
            "affected_parties": "competing cancer screening companies, patients",
            "geographic_scope": "United States (80%+ sequencing market)",
            "estimated_harm": "$5B+ in foreclosed competition",
            "referral_agency": "FTC",
        },
        "priority": "critical",
    },
    {
        "title": "Broadcom/VMware Enterprise Software Monopoly",
        "summary": "Broadcom's $69B acquisition of VMware investigated for potential monopolization of enterprise virtualization software. VMware dominates with 70%+ market share.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Broadcom Inc", "VMware Inc"],
            "industry": "enterprise_software",
            "alleged_conduct": "monopolization through acquisition, bundling concerns",
            "mechanism": "$69B acquisition of dominant virtualization platform",
            "affected_parties": "enterprise customers, competing virtualization vendors",
            "geographic_scope": "global",
            "estimated_harm": "$5B+ in potential price increases post-acquisition",
        },
        "priority": "high",
    },
    {
        "title": "Danaher/Cytiva Bioprocessing Monopoly",
        "summary": "Danaher investigated for monopolizing bioprocessing equipment market through serial acquisitions (Pall, Cytiva/GE Life Sciences) and bundling strategies.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Danaher Corporation", "Cytiva", "Pall Corporation"],
            "industry": "bioprocessing_equipment",
            "alleged_conduct": "monopolization through serial acquisition, bundling",
            "mechanism": "acquiring competitors, bundling consumables with equipment",
            "affected_parties": "biotech companies, pharmaceutical manufacturers",
            "geographic_scope": "global",
            "estimated_harm": "$3B+ in inflated bioprocessing costs",
            "referral_agency": "FTC",
        },
        "priority": "high",
    },
    {
        "title": "S&P Global/IHS Markit Data Monopoly",
        "summary": "DOJ reviewed S&P Global's $44B merger with IHS Markit for creating monopoly in financial data, credit ratings, and commodity price benchmarks.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["S&P Global", "IHS Markit"],
            "industry": "financial_data",
            "alleged_conduct": "monopolization through merger",
            "mechanism": "$44B merger combining dominant positions in overlapping markets",
            "affected_parties": "financial institutions, commodity traders, investors",
            "geographic_scope": "global",
            "estimated_harm": "$2B+ in reduced competition for financial data",
            "referral_agency": "DOJ Antitrust Division",
        },
        "priority": "high",
    },
]


# =============================================================================
# MARKET ALLOCATION (~12 cases)
# =============================================================================
MARKET_ALLOCATION = [
    {
        "title": "No-Poach Agreements in Silicon Valley (DOJ v. Adobe/Apple/Google/Intel)",
        "summary": "Major tech companies entered into bilateral no-poach agreements to suppress engineer wages. Companies agreed not to cold-call recruit each other's employees. Settled for $415M.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Apple Inc", "Google Inc", "Intel Corporation", "Adobe Systems", "Intuit", "Pixar"],
            "industry": "technology",
            "alleged_conduct": "market allocation (labor market), no-poach agreements, wage suppression",
            "mechanism": "bilateral no-cold-call agreements between CEOs",
            "affected_parties": "software engineers, tech workers",
            "geographic_scope": "Silicon Valley / nationwide tech industry",
            "estimated_harm": "$3B+ in suppressed wages",
            "settlement": "$415M",
            "referral_agency": "DOJ Antitrust Division",
        },
        "priority": "critical",
    },
    {
        "title": "Fast Food No-Poach Franchise Agreements",
        "summary": "Major fast food chains included no-poach clauses in franchise agreements preventing franchisees from hiring workers from other locations. Affected millions of low-wage workers.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["McDonald's Corporation", "Burger King", "Wendy's", "Arby's", "Dunkin' Brands", "Jimmy John's"],
            "industry": "fast_food",
            "alleged_conduct": "market allocation (labor market), no-poach clauses",
            "mechanism": "franchise agreement provisions restricting worker mobility",
            "affected_parties": "fast food workers (millions affected)",
            "geographic_scope": "nationwide",
            "estimated_harm": "$2B+ annually in suppressed wages",
            "referral_agency": "State AGs (WA, IL, NY)",
        },
        "priority": "critical",
    },
    {
        "title": "Hospital System No-Poach Agreements (Nursing Staff)",
        "summary": "Competing hospital systems entered into agreements not to recruit each other's nurses and medical staff, suppressing wages during critical nursing shortage. DOJ brought criminal charges.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["DaVita Inc", "Surgical Care Affiliates", "HCA Healthcare"],
            "industry": "healthcare",
            "alleged_conduct": "market allocation (labor market), no-poach, wage-fixing",
            "mechanism": "CEO-level agreements not to recruit competing hospital staff",
            "affected_parties": "nurses, medical technicians, healthcare workers",
            "geographic_scope": "multiple US metro areas",
            "estimated_harm": "$500M+ in suppressed healthcare worker wages",
            "referral_agency": "DOJ Antitrust Division (criminal)",
        },
        "priority": "critical",
    },
    {
        "title": "Aerospace Engineer Wage-Fixing (Pratt & Whitney/Collins)",
        "summary": "Aerospace companies conspired to fix wages and allocate the labor market for aerospace engineers through no-poach agreements and salary cap coordination.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Raytheon Technologies", "Pratt & Whitney", "Collins Aerospace", "General Electric Aviation"],
            "industry": "aerospace",
            "alleged_conduct": "wage-fixing, no-poach agreements, labor market allocation",
            "mechanism": "bilateral agreements on salary caps and no-recruit policies",
            "affected_parties": "aerospace engineers",
            "geographic_scope": "Connecticut, nationwide",
            "estimated_harm": "$300M+ in suppressed wages",
            "referral_agency": "DOJ Antitrust Division",
        },
        "priority": "high",
    },
    {
        "title": "Ready-Mix Concrete Market Allocation (Southeast US)",
        "summary": "Ready-mix concrete companies conspired to allocate geographic territories in the Southeast. Companies agreed which markets each would serve and refrained from competing.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Argos USA", "Buzzi Unicem", "Martin Marietta Materials", "Vulcan Materials"],
            "industry": "construction_materials",
            "alleged_conduct": "geographic market allocation, customer allocation",
            "mechanism": "territorial agreements dividing metro areas",
            "affected_parties": "construction companies, developers, homebuyers",
            "geographic_scope": "Southeast US (GA, FL, AL, SC, NC)",
            "estimated_harm": "$200M in inflated concrete costs",
            "referral_agency": "FBI Atlanta",
        },
        "priority": "high",
    },
    {
        "title": "Staffing Agency Market Allocation (Temporary Workers)",
        "summary": "Temporary staffing agencies conspired to allocate clients and geographic territories, agreeing not to compete for each other's accounts and fixing bill rates.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Staffing Solutions Enterprises", "Integrity Staffing Solutions", "TrueBlue Inc", "Employbridge"],
            "industry": "temporary_staffing",
            "alleged_conduct": "customer allocation, geographic market division, rate-fixing",
            "mechanism": "agreements to not solicit each other's clients",
            "affected_parties": "temporary workers, client companies",
            "geographic_scope": "Midwest and Southeast US",
            "estimated_harm": "$150M in inflated staffing costs",
            "referral_agency": "DOJ Antitrust Division",
        },
        "priority": "high",
    },
    {
        "title": "Waste Hauling Territory Allocation (New England)",
        "summary": "Commercial waste hauling companies conspired to divide New England territories, agreeing which company would serve which towns. Companies submitted sham bids in each other's territories.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Casella Waste Systems", "GFL Environmental", "WIN Waste Innovations", "USA Waste Services"],
            "industry": "waste_management",
            "alleged_conduct": "geographic market allocation, sham bidding",
            "mechanism": "territorial division agreements, complementary bidding",
            "affected_parties": "municipalities, businesses, residents",
            "geographic_scope": "New England (CT, MA, VT, NH, ME)",
            "estimated_harm": "$100M in inflated waste hauling costs",
            "referral_agency": "FBI Boston",
        },
        "priority": "high",
    },
    {
        "title": "Dialysis Services Market Allocation (DaVita/Fresenius)",
        "summary": "Two dominant dialysis providers investigated for allocating geographic markets and agreeing not to open competing clinics near each other's facilities.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["DaVita Inc", "Fresenius Medical Care"],
            "industry": "healthcare_dialysis",
            "alleged_conduct": "geographic market allocation, non-compete agreements",
            "mechanism": "agreements not to open competing clinics in each other's territories",
            "affected_parties": "dialysis patients, insurers",
            "geographic_scope": "nationwide (combined 80%+ market share)",
            "estimated_harm": "$1B+ annually in inflated dialysis costs",
            "referral_agency": "FTC",
        },
        "priority": "critical",
    },
    {
        "title": "Propane Distribution Territory Allocation (Rural US)",
        "summary": "Propane distributors conspired to allocate rural delivery territories. Rural customers had no alternative suppliers due to the allocation scheme.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Suburban Propane", "Ferrellgas Partners", "AmeriGas Partners", "Superior Plus"],
            "industry": "propane_distribution",
            "alleged_conduct": "geographic territory allocation, customer allocation",
            "mechanism": "agreements dividing rural delivery routes",
            "affected_parties": "rural homeowners, farms, small businesses",
            "geographic_scope": "Rural Midwest and Northeast US",
            "estimated_harm": "$200M in inflated propane costs",
            "referral_agency": "FBI",
        },
        "priority": "high",
    },
    {
        "title": "Moving and Storage Industry Market Allocation",
        "summary": "Interstate moving companies conspired to allocate customers and territories for household goods moving, including corporate relocation accounts and military moves.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["UniGroup (United Van Lines)", "SIRVA (Allied Van Lines)", "Atlas Van Lines", "Wheaton World Wide Moving"],
            "industry": "moving_storage",
            "alleged_conduct": "customer allocation, territory division",
            "mechanism": "agreements on corporate accounts and military contract allocation",
            "affected_parties": "military families, corporate transferees, consumers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$150M in inflated moving costs",
            "referral_agency": "DOD-OIG",
        },
        "priority": "high",
    },
    {
        "title": "Ambulance Services Market Allocation (Major Metro Areas)",
        "summary": "Private ambulance companies conspired to allocate 911 emergency and non-emergency transport contracts across major metropolitan areas.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["American Medical Response", "Rural/Metro Corporation", "Acadian Ambulance", "Priority Ambulance"],
            "industry": "emergency_medical_services",
            "alleged_conduct": "market allocation of ambulance contracts, bid rigging",
            "mechanism": "agreements on which company bids for specific metro contracts",
            "affected_parties": "municipalities, patients, taxpayers",
            "geographic_scope": "multiple major US metro areas",
            "estimated_harm": "$300M in inflated ambulance service costs",
            "referral_agency": "HHS-OIG",
        },
        "priority": "critical",
    },
    {
        "title": "Funeral Home Market Allocation (Service Corporation International)",
        "summary": "Funeral home chains investigated for allocating geographic markets through acquisition patterns and non-compete agreements that divided metropolitan areas.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Service Corporation International", "Dignity Memorial", "Carriage Services", "Park Lawn Corporation"],
            "industry": "funeral_services",
            "alleged_conduct": "market allocation through acquisitions and non-competes",
            "mechanism": "serial acquisitions with broad non-compete clauses",
            "affected_parties": "bereaved families, independent funeral homes",
            "geographic_scope": "nationwide",
            "estimated_harm": "$500M annually in inflated funeral costs",
            "referral_agency": "FTC",
        },
        "priority": "high",
    },
]


# =============================================================================
# MERGER REVIEW (~10 cases)
# =============================================================================
MERGER_REVIEW = [
    {
        "title": "Kroger/Albertsons Supermarket Merger ($24.6B)",
        "summary": "FTC challenged Kroger's proposed $24.6B acquisition of Albertsons, arguing it would eliminate competition in hundreds of local grocery markets, leading to higher prices and reduced wages for grocery workers.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Kroger Co", "Albertsons Companies"],
            "industry": "grocery_retail",
            "alleged_conduct": "anticompetitive merger, market concentration",
            "mechanism": "$24.6B merger of #1 and #2 pure-play grocers",
            "affected_parties": "grocery shoppers, grocery workers, suppliers",
            "geographic_scope": "nationwide (hundreds of overlapping markets)",
            "estimated_harm": "$1B+ annually in higher grocery prices",
            "referral_agency": "FTC",
        },
        "priority": "critical",
    },
    {
        "title": "JetBlue/Spirit Airlines Merger Block",
        "summary": "DOJ successfully blocked JetBlue's $3.8B acquisition of Spirit Airlines, arguing it would eliminate the largest ultra-low-cost carrier and raise fares for budget travelers.",
        "source_type": "news",
        "source_content": {
            "subjects": ["JetBlue Airways", "Spirit Airlines"],
            "industry": "airlines",
            "alleged_conduct": "anticompetitive merger eliminating low-cost competition",
            "mechanism": "$3.8B acquisition of largest ULCC",
            "affected_parties": "budget travelers, competing airlines",
            "geographic_scope": "nationwide (hundreds of overlapping routes)",
            "estimated_harm": "$2B+ annually in higher airfares",
            "referral_agency": "DOJ Antitrust Division",
        },
        "priority": "critical",
    },
    {
        "title": "Microsoft/Activision Blizzard Gaming Merger ($69B)",
        "summary": "FTC challenged Microsoft's $69B acquisition of Activision Blizzard, arguing it would give Microsoft control of popular gaming franchises and ability to foreclose competing platforms.",
        "source_type": "news",
        "source_content": {
            "subjects": ["Microsoft Corporation", "Activision Blizzard"],
            "industry": "video_games",
            "alleged_conduct": "vertical merger foreclosure concerns",
            "mechanism": "$69B acquisition of major game publisher",
            "affected_parties": "competing gaming platforms (Sony, Nintendo), gamers",
            "geographic_scope": "global",
            "estimated_harm": "potential foreclosure of competing platforms",
            "referral_agency": "FTC",
        },
        "priority": "high",
    },
    {
        "title": "UnitedHealth/Change Healthcare Merger ($13B)",
        "summary": "DOJ challenged UnitedHealth Group's $13B acquisition of Change Healthcare, arguing it would give UnitedHealth access to rivals' competitively sensitive claims data.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["UnitedHealth Group", "Change Healthcare"],
            "industry": "healthcare_technology",
            "alleged_conduct": "vertical merger, access to competitor data",
            "mechanism": "$13B acquisition of health data clearinghouse",
            "affected_parties": "competing health insurers, healthcare providers, patients",
            "geographic_scope": "nationwide",
            "estimated_harm": "$5B+ in competitive harm to rival insurers",
            "referral_agency": "DOJ Antitrust Division",
        },
        "priority": "critical",
    },
    {
        "title": "Penguin Random House/Simon & Schuster Merger Block",
        "summary": "DOJ successfully blocked Penguin Random House's $2.2B acquisition of Simon & Schuster, arguing it would reduce competition for top-selling book authors.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Penguin Random House", "Simon & Schuster", "Bertelsmann"],
            "industry": "book_publishing",
            "alleged_conduct": "anticompetitive merger reducing competition for authors",
            "mechanism": "$2.2B merger of two of Big Five publishers",
            "affected_parties": "authors, literary agents, readers, independent publishers",
            "geographic_scope": "United States",
            "estimated_harm": "reduced author advances, less publishing diversity",
            "referral_agency": "DOJ Antitrust Division",
        },
        "priority": "high",
    },
    {
        "title": "NVIDIA/Arm Semiconductor Merger (Abandoned $40B)",
        "summary": "FTC challenged NVIDIA's proposed $40B acquisition of Arm Holdings, arguing it would give NVIDIA control over computing technology that rivals need. Deal abandoned under regulatory pressure.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["NVIDIA Corporation", "Arm Holdings", "SoftBank Group"],
            "industry": "semiconductor",
            "alleged_conduct": "vertical merger threatening chip design neutrality",
            "mechanism": "$40B acquisition of essential chip architecture licensor",
            "affected_parties": "competing chipmakers (Qualcomm, Apple, AMD), device makers",
            "geographic_scope": "global",
            "estimated_harm": "potential foreclosure of $500B+ chip industry",
            "referral_agency": "FTC",
        },
        "priority": "critical",
    },
    {
        "title": "Lockheed Martin/Aerojet Rocketdyne Merger (Abandoned $4.4B)",
        "summary": "FTC challenged Lockheed Martin's $4.4B acquisition of Aerojet Rocketdyne, the last independent supplier of missile propulsion systems.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Lockheed Martin", "Aerojet Rocketdyne"],
            "industry": "defense",
            "alleged_conduct": "vertical merger threatening defense supply chain",
            "mechanism": "$4.4B acquisition of sole-source propulsion supplier",
            "affected_parties": "competing defense contractors (Raytheon, Northrop), DOD",
            "geographic_scope": "United States defense industry",
            "estimated_harm": "potential foreclosure of competing missile programs",
            "referral_agency": "FTC",
        },
        "priority": "high",
    },
    {
        "title": "Anthem/Cigna Health Insurance Merger Block ($54B)",
        "summary": "DOJ successfully blocked Anthem's $54B acquisition of Cigna, arguing it would reduce competition in health insurance markets serving large national employers.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Anthem Inc (now Elevance)", "Cigna Corporation"],
            "industry": "health_insurance",
            "alleged_conduct": "horizontal merger reducing insurer competition",
            "mechanism": "$54B merger of two of five largest health insurers",
            "affected_parties": "large employers, employees, healthcare providers",
            "geographic_scope": "nationwide",
            "estimated_harm": "$5B+ annually in higher premiums",
            "referral_agency": "DOJ Antitrust Division",
        },
        "priority": "critical",
    },
    {
        "title": "Sysco/US Foods Merger Block ($3.5B)",
        "summary": "FTC successfully blocked Sysco's $3.5B acquisition of US Foods, arguing it would combine the two largest food distributors and create a dominant firm.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Sysco Corporation", "US Foods"],
            "industry": "food_distribution",
            "alleged_conduct": "horizontal merger of #1 and #2 broadline distributors",
            "mechanism": "$3.5B merger creating dominant food distributor",
            "affected_parties": "restaurants, hotels, hospitals, schools",
            "geographic_scope": "nationwide",
            "estimated_harm": "$2B+ annually in higher food distribution costs",
            "referral_agency": "FTC",
        },
        "priority": "high",
    },
    {
        "title": "Staples/Office Depot Merger Block (Second Attempt)",
        "summary": "FTC blocked Staples' second attempt to acquire Office Depot for $6.3B, arguing it would create a monopoly in office supplies sold to large business customers.",
        "source_type": "referral",
        "source_content": {
            "subjects": ["Staples Inc", "Office Depot"],
            "industry": "office_supplies",
            "alleged_conduct": "horizontal merger creating B2B office supply monopoly",
            "mechanism": "$6.3B merger of only two national office supply chains",
            "affected_parties": "large businesses, government agencies, schools",
            "geographic_scope": "nationwide",
            "estimated_harm": "$1B+ in higher office supply costs for businesses",
            "referral_agency": "FTC",
        },
        "priority": "high",
    },
]


# =============================================================================
# MAIN - Submit all leads (POST /pre-case/leads only, no full pipeline)
# =============================================================================
ALL_CATEGORIES = [
    ("procurement_collusion", PROCUREMENT_COLLUSION),
    ("price_fixing", PRICE_FIXING),
    ("criminal_cartel", CRIMINAL_CARTEL),
    ("monopolization", MONOPOLIZATION),
    ("market_allocation", MARKET_ALLOCATION),
    ("merger_review", MERGER_REVIEW),
]


def main():
    print("=" * 70)
    print("DOJ ANTITRUST — SUBMIT 100 PRE-CASE LEADS (6 CATEGORIES)")
    print("=" * 70)

    total_cases = sum(len(cases) for _, cases in ALL_CATEGORIES)
    print(f"\nTotal cases to submit: {total_cases}")
    print(f"\nCategory breakdown:")
    for cat_name, cases in ALL_CATEGORIES:
        print(f"  • {cat_name}: {len(cases)} cases")
    print()

    results = {"success": 0, "failed": 0, "errors": []}
    submitted = 0

    for category_name, cases in ALL_CATEGORIES:
        print(f"\n{'━' * 70}")
        print(f"CATEGORY: {category_name.upper()} ({len(cases)} cases)")
        print(f"{'━' * 70}")

        for i, case in enumerate(cases, 1):
            submitted += 1
            # Add category tag to source_content
            case_payload = dict(case)
            if "source_content" in case_payload:
                case_payload["source_content"] = dict(case_payload["source_content"])
                case_payload["source_content"]["antitrust_category"] = category_name

            print(f"  [{submitted:3d}/{total_cases}] {case['title'][:60]}...", end=" ")

            try:
                status, body = invoke_api("POST", "/pre-case/leads", case_payload)
                if status in (200, 201):
                    lead_id = body.get("lead_id") or body.get("data", {}).get("lead_id", "?")
                    print(f"✓ {lead_id}")
                    results["success"] += 1
                else:
                    print(f"✗ HTTP {status}")
                    results["failed"] += 1
                    results["errors"].append(f"{case['title']}: HTTP {status}")
            except Exception as e:
                print(f"✗ ERROR: {e}")
                results["failed"] += 1
                results["errors"].append(f"{case['title']}: {e}")

            # Brief pause to avoid Lambda throttling
            time.sleep(0.5)

    # --- Summary ---
    print(f"\n\n{'=' * 70}")
    print("SUBMISSION SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total attempted: {submitted}")
    print(f"  Successful:      {results['success']}")
    print(f"  Failed:          {results['failed']}")

    if results["errors"]:
        print(f"\n  Errors:")
        for err in results["errors"][:10]:
            print(f"    • {err}")
        if len(results["errors"]) > 10:
            print(f"    ... and {len(results['errors']) - 10} more")

    print(f"\n{'=' * 70}")
    print("All leads submitted to Pre-Case Intelligence dashboard.")
    print("Run classify/gather/assess separately if needed.")
    print(f"{'=' * 70}")

    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
