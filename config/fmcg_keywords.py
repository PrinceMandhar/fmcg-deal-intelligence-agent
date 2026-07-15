"""
config/fmcg_keywords.py
------------------------
Relevance taxonomy used by the Relevance Agent to decide whether an article
is actually about an FMCG deal (as opposed to generic business news).

This is intentionally a plain, editable keyword list rather than a black-box
model, so the "relevance check logic" the assignment asks for is explainable
in one glance.
"""

FMCG_COMPANIES = [
    # Indian FMCG majors
    "hindustan unilever", "hul", "itc limited", "itc ltd", "nestle india",
    "britannia", "dabur", "marico", "godrej consumer", "colgate-palmolive",
    "colgate palmolive", "patanjali", "emami", "tata consumer", "adani wilmar",
    "varun beverages", "parle", "parle agro", "rspl", "vlcc", "amul", "gcmmf",
    "bikaji", "haldiram", "mrs bectors", "prataap snacks", "dfm foods",
    "jyothy labs", "wipro consumer", "himalaya wellness", "usha international",
    "cavinkare", "zydus wellness", "bajaj consumer", "gillette india",
    "procter & gamble india", "p&g india", "reckitt benckiser india",
    "mondelez india", "cadbury india", "pepsico india", "coca-cola india",
    "united spirits", "radico khaitan", "united breweries",
    # Global FMCG majors (deals often cross-border)
    "unilever", "nestle", "procter & gamble", "p&g", "pepsico", "coca-cola",
    "mondelez", "danone", "kraft heinz", "colgate-palmolive global",
    "reckitt benckiser", "kimberly-clark", "general mills", "kellanova",
    "l'oreal", "estee lauder", "beiersdorf", "henkel", "diageo",
]

DEAL_KEYWORDS = [
    "acquire", "acquires", "acquired", "acquisition", "merger", "merges",
    "stake", "invest", "investment", "invests", "funding", "raises funds",
    "ipo", "public offering", "joint venture", "jv", "buyout", "divest",
    "divestment", "stake sale", "equity stake", "minority stake",
    "majority stake", "takeover", "strategic partnership", "private equity",
    "venture capital", "series a", "series b", "series c", "valuation",
    "deal value", "crore deal", "million deal", "billion deal", "consolidat",
]

SECTOR_HINTS = [
    "fmcg", "consumer goods", "packaged food", "beverage", "snack", "dairy",
    "personal care", "home care", "cosmetics", "skincare", "haircare",
    "oral care", "staples", "consumer products", "retail brand",
]

# Minimum combined relevance score (0-1) to pass the filter
RELEVANCE_THRESHOLD = 0.35
