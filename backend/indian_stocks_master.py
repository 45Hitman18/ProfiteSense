"""
indian_stocks_master.py — Master Stock Index for Indian Equities (NSE/BSE)
==========================================================================
Provides fast in-memory prefix, alias, substring, and typo-tolerant fuzzy
matching for Indian listed stocks, enriched with live/cached quotes.
"""

import time
import re
from typing import List, Dict, Any, Optional

# Top 100+ Liquid Indian Equities & Major Benchmarks (NSE/BSE)
INDIAN_STOCKS_DATA = [
    # Benchmarks
    {"ticker": "^NSEI", "symbol": "NIFTY 50", "name": "NIFTY 50 Index", "aliases": ["Nifty", "Nifty 50", "NSE", "Benchmark"], "sector": "Benchmark"},
    {"ticker": "^BSESN", "symbol": "SENSEX", "name": "BSE SENSEX Index", "aliases": ["Sensex", "BSE", "BSE 30", "Bombay Stock Exchange"], "sector": "Benchmark"},

    # Mega Cap / NIFTY 50
    {"ticker": "RELIANCE.NS", "symbol": "RELIANCE", "name": "Reliance Industries Ltd", "aliases": ["Reliance", "RIL", "Jio", "Mukesh Ambani", "Retail", "Refinery"], "sector": "Energy & Petrochemicals"},
    {"ticker": "TCS.NS", "symbol": "TCS", "name": "Tata Consultancy Services Ltd", "aliases": ["TCS", "Tata Consultancy", "Tata Tech", "IT"], "sector": "Information Technology"},
    {"ticker": "HDFCBANK.NS", "symbol": "HDFCBANK", "name": "HDFC Bank Ltd", "aliases": ["HDFC", "HDFC Bank", "HDFC Ltd", "Banking"], "sector": "Banking & Finance"},
    {"ticker": "INFY.NS", "symbol": "INFY", "name": "Infosys Ltd", "aliases": ["Infosys", "Infy", "IT Services", "Narayana Murthy"], "sector": "Information Technology"},
    {"ticker": "ICICIBANK.NS", "symbol": "ICICIBANK", "name": "ICICI Bank Ltd", "aliases": ["ICICI", "ICICI Bank", "Private Bank"], "sector": "Banking & Finance"},
    {"ticker": "SBIN.NS", "symbol": "SBIN", "name": "State Bank of India", "aliases": ["SBI", "State Bank", "State Bank of India", "PSU Bank"], "sector": "Banking & Finance"},
    {"ticker": "BHARTIARTL.NS", "symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd", "aliases": ["Airtel", "Bharti Airtel", "Telecom", "Sunil Mittal"], "sector": "Telecommunications"},
    {"ticker": "ITC.NS", "symbol": "ITC", "name": "ITC Ltd", "aliases": ["ITC", "Imperial Tobacco", "Cigarettes", "FMCG", "Hotels"], "sector": "Consumer Goods (FMCG)"},
    {"ticker": "TATAMOTORS.NS", "symbol": "TATAMOTORS", "name": "Tata Motors Ltd", "aliases": ["Tata Motors", "TaMo", "JLR", "Jaguar", "Land Rover", "Tata EV"], "sector": "Automobile"},
    {"ticker": "LT.NS", "symbol": "LT", "name": "Larsen & Toubro Ltd", "aliases": ["L&T", "Larsen", "Larsen and Toubro", "Infrastructure", "Construction"], "sector": "Engineering & Construction"},
    {"ticker": "KOTAKBANK.NS", "symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Ltd", "aliases": ["Kotak", "Kotak Bank", "Uday Kotak"], "sector": "Banking & Finance"},
    {"ticker": "HINDUNILVR.NS", "symbol": "HINDUNILVR", "name": "Hindustan Unilever Ltd", "aliases": ["HUL", "Unilever", "Hindustan Unilever", "Surf", "Dove"], "sector": "Consumer Goods (FMCG)"},
    {"ticker": "AXISBANK.NS", "symbol": "AXISBANK", "name": "Axis Bank Ltd", "aliases": ["Axis", "Axis Bank", "UTI Bank"], "sector": "Banking & Finance"},
    {"ticker": "BAJFINANCE.NS", "symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd", "aliases": ["Bajaj Finance", "Bajaj", "NBFC", "Consumer Finance"], "sector": "Banking & Finance"},
    {"ticker": "MARUTI.NS", "symbol": "MARUTI", "name": "Maruti Suzuki India Ltd", "aliases": ["Maruti", "Maruti Suzuki", "Suzuki", "Swift", "Cars"], "sector": "Automobile"},
    {"ticker": "SUNPHARMA.NS", "symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries Ltd", "aliases": ["Sun Pharma", "Sun Pharmaceutical", "Dilip Shanghvi", "Pharma"], "sector": "Pharmaceuticals"},
    {"ticker": "TITAN.NS", "symbol": "TITAN", "name": "Titan Company Ltd", "aliases": ["Titan", "Tanishq", "Fastrack", "Jewellery", "Watches"], "sector": "Consumer Discretionary"},
    {"ticker": "ASIANPAINT.NS", "symbol": "ASIANPAINT", "name": "Asian Paints Ltd", "aliases": ["Asian Paints", "Paints", "Home Decor"], "sector": "Materials & Paints"},
    {"ticker": "WIPRO.NS", "symbol": "WIPRO", "name": "Wipro Ltd", "aliases": ["Wipro", "Azim Premji", "IT"], "sector": "Information Technology"},
    {"ticker": "HCLTECH.NS", "symbol": "HCLTECH", "name": "HCL Technologies Ltd", "aliases": ["HCL", "HCL Tech", "Shiv Nadar"], "sector": "Information Technology"},
    {"ticker": "ADANIENT.NS", "symbol": "ADANIENT", "name": "Adani Enterprises Ltd", "aliases": ["Adani", "Adani Enterprises", "Gautam Adani", "Flagship"], "sector": "Metals & Mining / Conglomerate"},
    {"ticker": "ADANIPORTS.NS", "symbol": "ADANIPORTS", "name": "Adani Ports & Special Economic Zone", "aliases": ["Adani Ports", "APSEZ", "Mundra", "Ports"], "sector": "Infrastructure & Logistics"},
    {"ticker": "NTPC.NS", "symbol": "NTPC", "name": "NTPC Ltd", "aliases": ["NTPC", "National Thermal Power", "Power", "Green Energy"], "sector": "Power & Utilities"},
    {"ticker": "POWERGRID.NS", "symbol": "POWERGRID", "name": "Power Grid Corporation of India", "aliases": ["Power Grid", "PGCIL", "Transmission"], "sector": "Power & Utilities"},
    {"ticker": "ONGC.NS", "symbol": "ONGC", "name": "Oil & Natural Gas Corporation Ltd", "aliases": ["ONGC", "Oil and Natural Gas", "Crude", "Petroleum"], "sector": "Energy & Petrochemicals"},
    {"ticker": "COALINDIA.NS", "symbol": "COALINDIA", "name": "Coal India Ltd", "aliases": ["Coal India", "CIL", "Coal Mining"], "sector": "Metals & Mining"},
    {"ticker": "ULTRACEMCO.NS", "symbol": "ULTRACEMCO", "name": "UltraTech Cement Ltd", "aliases": ["UltraTech", "UltraTech Cement", "Birla Cement"], "sector": "Cement & Building Materials"},
    {"ticker": "JSWSTEEL.NS", "symbol": "JSWSTEEL", "name": "JSW Steel Ltd", "aliases": ["JSW Steel", "JSW", "Sajjan Jindal", "Steel"], "sector": "Metals & Mining"},
    {"ticker": "TATASTEEL.NS", "symbol": "TATASTEEL", "name": "Tata Steel Ltd", "aliases": ["Tata Steel", "TISCO", "Steel"], "sector": "Metals & Mining"},
    {"ticker": "M&M.NS", "symbol": "M&M", "name": "Mahindra & Mahindra Ltd", "aliases": ["M&M", "Mahindra", "Mahindra and Mahindra", "Scorpio", "Thar", "Tractors"], "sector": "Automobile"},
    {"ticker": "NESTLEIND.NS", "symbol": "NESTLEIND", "name": "Nestle India Ltd", "aliases": ["Nestle", "Maggi", "Nescafe", "KitKat"], "sector": "Consumer Goods (FMCG)"},
    {"ticker": "BAJAJFINSV.NS", "symbol": "BAJAJFINSV", "name": "Bajaj Finserv Ltd", "aliases": ["Bajaj Finserv", "Finserv", "Insurance"], "sector": "Banking & Finance"},
    {"ticker": "GRASIM.NS", "symbol": "GRASIM", "name": "Grasim Industries Ltd", "aliases": ["Grasim", "Aditya Birla", "Birla Opus"], "sector": "Materials & Paints"},
    {"ticker": "TECHM.NS", "symbol": "TECHM", "name": "Tech Mahindra Ltd", "aliases": ["Tech Mahindra", "TechM", "Mahindra IT"], "sector": "Information Technology"},
    {"ticker": "HINDALCO.NS", "symbol": "HINDALCO", "name": "Hindalco Industries Ltd", "aliases": ["Hindalco", "Novelis", "Aluminium", "Copper"], "sector": "Metals & Mining"},
    {"ticker": "DRREDDY.NS", "symbol": "DRREDDY", "name": "Dr. Reddy's Laboratories Ltd", "aliases": ["Dr Reddys", "Dr Reddy", "Pharma"], "sector": "Pharmaceuticals"},
    {"ticker": "CIPLA.NS", "symbol": "CIPLA", "name": "Cipla Ltd", "aliases": ["Cipla", "Pharma", "Inhalers"], "sector": "Pharmaceuticals"},
    {"ticker": "APOLLOHOSP.NS", "symbol": "APOLLOHOSP", "name": "Apollo Hospitals Enterprise Ltd", "aliases": ["Apollo Hospitals", "Apollo", "Healthcare"], "sector": "Healthcare & Hospitals"},
    {"ticker": "DIVISLAB.NS", "symbol": "DIVISLAB", "name": "Divi's Laboratories Ltd", "aliases": ["Divis", "Divis Lab", "API Pharma"], "sector": "Pharmaceuticals"},
    {"ticker": "EICHERMOT.NS", "symbol": "EICHERMOT", "name": "Eicher Motors Ltd", "aliases": ["Eicher", "Royal Enfield", "Bullet", "Hunter"], "sector": "Automobile"},
    {"ticker": "BAJAJ-AUTO.NS", "symbol": "BAJAJ-AUTO", "name": "Bajaj Auto Ltd", "aliases": ["Bajaj Auto", "Pulsar", "Chetak", "Two Wheeler"], "sector": "Automobile"},
    {"ticker": "HEROMOTOCO.NS", "symbol": "HEROMOTOCO", "name": "Hero MotoCorp Ltd", "aliases": ["Hero", "Hero MotoCorp", "Hero Motors", "Hero Moto", "Splendor", "Hero Honda"], "sector": "Automobile"},
    {"ticker": "HEROMOTORS.NS", "symbol": "HEROMOTORS", "name": "Hero Motors Ltd", "aliases": ["Hero Motors", "Hero Motors Ltd", "Hero Group", "Hero Components"], "sector": "Automobile"},
    {"ticker": "BRITANNIA.NS", "symbol": "BRITANNIA", "name": "Britannia Industries Ltd", "aliases": ["Britannia", "Good Day", "Biscuits"], "sector": "Consumer Goods (FMCG)"},
    {"ticker": "TATACONSUM.NS", "symbol": "TATACONSUM", "name": "Tata Consumer Products Ltd", "aliases": ["Tata Consumer", "Tata Tea", "Tata Salt", "Sampann"], "sector": "Consumer Goods (FMCG)"},
    {"ticker": "INDUSINDBK.NS", "symbol": "INDUSINDBK", "name": "IndusInd Bank Ltd", "aliases": ["IndusInd", "IndusInd Bank", "Hinduja"], "sector": "Banking & Finance"},
    {"ticker": "BPCL.NS", "symbol": "BPCL", "name": "Bharat Petroleum Corp Ltd", "aliases": ["BPCL", "Bharat Petroleum", "Oil Refinery"], "sector": "Energy & Petrochemicals"},
    {"ticker": "SHRIRAMFIN.NS", "symbol": "SHRIRAMFIN", "name": "Shriram Finance Ltd", "aliases": ["Shriram Finance", "Shriram Transport", "STFC"], "sector": "Banking & Finance"},
    {"ticker": "LTIM.NS", "symbol": "LTIM", "name": "LTIMindtree Ltd", "aliases": ["LTIMindtree", "Mindtree", "L&T Infotech"], "sector": "Information Technology"},
    {"ticker": "TRENT.NS", "symbol": "TRENT", "name": "Trent Ltd", "aliases": ["Trent", "Zudio", "Westside", "Tata Retail"], "sector": "Consumer Discretionary (Retail)"},
    {"ticker": "BEL.NS", "symbol": "BEL", "name": "Bharat Electronics Ltd", "aliases": ["BEL", "Bharat Electronics", "Defense"], "sector": "Defense & Electronics"},

    # High-Volume Liquid & Popular Mid/Large Caps
    {"ticker": "ZOMATO.NS", "symbol": "ZOMATO", "name": "Zomato Ltd", "aliases": ["Zomato", "Blinkit", "Food Delivery", "Quick Commerce"], "sector": "Consumer Tech / Internet"},
    {"ticker": "JIOFIN.NS", "symbol": "JIOFIN", "name": "Jio Financial Services Ltd", "aliases": ["Jio Financial", "Jio Fin", "JFS", "BlackRock Jio"], "sector": "Banking & Finance"},
    {"ticker": "HAL.NS", "symbol": "HAL", "name": "Hindustan Aeronautics Ltd", "aliases": ["HAL", "Hindustan Aeronautics", "Defense", "Tejas"], "sector": "Aerospace & Defense"},
    {"ticker": "MAZDOCK.NS", "symbol": "MAZDOCK", "name": "Mazagon Dock Shipbuilders Ltd", "aliases": ["Mazagon Dock", "Mazdock", "Submarines", "Defense Ship"], "sector": "Defense & Shipbuilding"},
    {"ticker": "COCHINSHIP.NS", "symbol": "COCHINSHIP", "name": "Cochin Shipyard Ltd", "aliases": ["Cochin Shipyard", "Aircraft Carrier", "Shipbuilding"], "sector": "Defense & Shipbuilding"},
    {"ticker": "BHEL.NS", "symbol": "BHEL", "name": "Bharat Heavy Electricals Ltd", "aliases": ["BHEL", "Bharat Heavy", "Power Equipment"], "sector": "Capital Goods"},
    {"ticker": "IRFC.NS", "symbol": "IRFC", "name": "Indian Railway Finance Corporation", "aliases": ["IRFC", "Railway Finance", "Railway PSU"], "sector": "Financial Services (PSU)"},
    {"ticker": "RVNL.NS", "symbol": "RVNL", "name": "Rail Vikas Nigam Ltd", "aliases": ["RVNL", "Rail Vikas", "Railway Infrastructure"], "sector": "Railways & Construction"},
    {"ticker": "IRCTC.NS", "symbol": "IRCTC", "name": "Indian Railway Catering and Tourism Corp", "aliases": ["IRCTC", "Railways", "Train Tickets", "Rail Neer"], "sector": "Travel & Tourism"},
    {"ticker": "IREDA.NS", "symbol": "IREDA", "name": "Indian Renewable Energy Dev Agency", "aliases": ["IREDA", "Green Energy PSU", "Renewable Financing"], "sector": "Financial Services (Green)"},
    {"ticker": "SUZLON.NS", "symbol": "SUZLON", "name": "Suzlon Energy Ltd", "aliases": ["Suzlon", "Wind Energy", "Turbines"], "sector": "Renewable Energy"},
    {"ticker": "YESBANK.NS", "symbol": "YESBANK", "name": "Yes Bank Ltd", "aliases": ["Yes Bank", "Private Bank"], "sector": "Banking & Finance"},
    {"ticker": "OLAELEC.NS", "symbol": "OLAELEC", "name": "Ola Electric Mobility Ltd", "aliases": ["Ola Electric", "Ola EV", "Bhavish Aggarwal"], "sector": "Automobile (EV)"},
    {"ticker": "DMART.NS", "symbol": "DMART", "name": "Avenue Supermarts Ltd (DMart)", "aliases": ["DMart", "Avenue Supermarts", "Radhakishan Damani", "Retail"], "sector": "Consumer Discretionary (Retail)"},
    {"ticker": "MOTHERSON.NS", "symbol": "MOTHERSON", "name": "Samvardhana Motherson International Ltd", "aliases": ["Motherson", "Motherson Sumi", "Auto Ancillary"], "sector": "Automobile Ancillary"},
    {"ticker": "TVSMOTOR.NS", "symbol": "TVSMOTOR", "name": "TVS Motor Company Ltd", "aliases": ["TVS", "TVS Motor", "Apache", "Jupiter", "iQube"], "sector": "Automobile"},
    {"ticker": "BAJAJHLDNG.NS", "symbol": "BAJAJHLDNG", "name": "Bajaj Holdings & Investment Ltd", "aliases": ["Bajaj Holdings", "Bajaj Holding"], "sector": "Banking & Finance"},
    {"ticker": "INDIGO.NS", "symbol": "INDIGO", "name": "InterGlobe Aviation Ltd (IndiGo)", "aliases": ["IndiGo", "InterGlobe", "Airlines", "Aviation"], "sector": "Aviation & Airlines"},
    {"ticker": "SWIGGY.NS", "symbol": "SWIGGY", "name": "Swiggy Ltd", "aliases": ["Swiggy", "Instamart", "Food Delivery", "Quick Commerce"], "sector": "Consumer Tech / Internet"},
    {"ticker": "IDEA.NS", "symbol": "IDEA", "name": "Vodafone Idea Ltd", "aliases": ["Vodafone Idea", "VI", "Idea Cellular", "Telecom"], "sector": "Telecommunications"},
    {"ticker": "VEDL.NS", "symbol": "VEDL", "name": "Vedanta Ltd", "aliases": ["Vedanta", "Anil Agarwal", "Sterlite", "Mining"], "sector": "Metals & Mining"},
    {"ticker": "TATAPOWER.NS", "symbol": "TATAPOWER", "name": "Tata Power Company Ltd", "aliases": ["Tata Power", "Solar", "EV Charging", "Renewable"], "sector": "Power & Utilities"},
    {"ticker": "PAYTM.NS", "symbol": "PAYTM", "name": "One97 Communications Ltd (Paytm)", "aliases": ["Paytm", "One97", "Vijay Shekhar Sharma", "Fintech"], "sector": "Fintech"},
    {"ticker": "POLICYBZR.NS", "symbol": "POLICYBZR", "name": "PB Fintech Ltd (PolicyBazaar)", "aliases": ["PolicyBazaar", "PB Fintech", "PaisaBazaar"], "sector": "Fintech / Insurance"},
    {"ticker": "DELHIVERY.NS", "symbol": "DELHIVERY", "name": "Delhivery Ltd", "aliases": ["Delhivery", "Logistics", "E-commerce Delivery"], "sector": "Logistics & Supply Chain"},
    {"ticker": "NYKAA.NS", "symbol": "NYKAA", "name": "FSN E-Commerce Ventures (Nykaa)", "aliases": ["Nykaa", "Falguni Nayar", "Beauty", "Cosmetics"], "sector": "E-Commerce & Retail"},
    {"ticker": "IDFCFIRSTB.NS", "symbol": "IDFCFIRSTB", "name": "IDFC First Bank Ltd", "aliases": ["IDFC First", "IDFC Bank", "V Vaidyanathan"], "sector": "Banking & Finance"},
    {"ticker": "FEDERALBNK.NS", "symbol": "FEDERALBNK", "name": "Federal Bank Ltd", "aliases": ["Federal Bank", "Kerala Bank"], "sector": "Banking & Finance"},
    {"ticker": "PNB.NS", "symbol": "PNB", "name": "Punjab National Bank", "aliases": ["PNB", "Punjab National Bank", "PSU Bank"], "sector": "Banking & Finance"},
    {"ticker": "BANKBARODA.NS", "symbol": "BANKBARODA", "name": "Bank of Baroda", "aliases": ["Bank of Baroda", "BOB", "PSU Bank"], "sector": "Banking & Finance"},
    {"ticker": "CANBK.NS", "symbol": "CANBK", "name": "Canara Bank", "aliases": ["Canara Bank", "Canara", "PSU Bank"], "sector": "Banking & Finance"},
    {"ticker": "UNIONBANK.NS", "symbol": "UNIONBANK", "name": "Union Bank of India", "aliases": ["Union Bank", "UBI", "PSU Bank"], "sector": "Banking & Finance"},
    {"ticker": "DLF.NS", "symbol": "DLF", "name": "DLF Ltd", "aliases": ["DLF", "Delhi Land and Finance", "Real Estate"], "sector": "Real Estate"},
    {"ticker": "PRESTIGE.NS", "symbol": "PRESTIGE", "name": "Prestige Estates Projects Ltd", "aliases": ["Prestige Estates", "Prestige", "Real Estate"], "sector": "Real Estate"},
    {"ticker": "IOC.NS", "symbol": "IOC", "name": "Indian Oil Corporation Ltd", "aliases": ["IOC", "Indian Oil", "Servo", "Refinery"], "sector": "Energy & Petrochemicals"},
    {"ticker": "GAIL.NS", "symbol": "GAIL", "name": "GAIL (India) Ltd", "aliases": ["GAIL", "Gas Authority", "Natural Gas"], "sector": "Energy & Utilities"},
    {"ticker": "SIEMENS.NS", "symbol": "SIEMENS", "name": "Siemens Ltd", "aliases": ["Siemens", "Industrial Automation", "Railways"], "sector": "Capital Goods"},
    {"ticker": "ABB.NS", "symbol": "ABB", "name": "ABB India Ltd", "aliases": ["ABB", "Robotics", "Power Grids"], "sector": "Capital Goods"},
    {"ticker": "VBL.NS", "symbol": "VBL", "name": "Varun Beverages Ltd", "aliases": ["Varun Beverages", "VBL", "Pepsi Bottler", "Sting"], "sector": "Consumer Goods (Beverages)"},
    {"ticker": "POLYCAB.NS", "symbol": "POLYCAB", "name": "Polycab India Ltd", "aliases": ["Polycab", "Wires", "Cables", "FMEG"], "sector": "Consumer Electricals"},
    {"ticker": "HAVELLS.NS", "symbol": "HAVELLS", "name": "Havells India Ltd", "aliases": ["Havells", "Lloyd", "Fans", "Lighting"], "sector": "Consumer Electricals"},
    {"ticker": "PIDILITIND.NS", "symbol": "PIDILITIND", "name": "Pidilite Industries Ltd", "aliases": ["Pidilite", "Fevicol", "FeviKwik", "Adhesives"], "sector": "Chemicals & Adhesives"},
    {"ticker": "GODREJCP.NS", "symbol": "GODREJCP", "name": "Godrej Consumer Products Ltd", "aliases": ["Godrej Consumer", "Godrej CP", "Good Knight", "Cinthol"], "sector": "Consumer Goods (FMCG)"},
    {"ticker": "DABUR.NS", "symbol": "DABUR", "name": "Dabur India Ltd", "aliases": ["Dabur", "Chyawanprash", "Ayurveda", "Real Juice"], "sector": "Consumer Goods (FMCG)"},
    {"ticker": "AMBUJACEM.NS", "symbol": "AMBUJACEM", "name": "Ambuja Cements Ltd", "aliases": ["Ambuja", "Ambuja Cement", "Adani Cement"], "sector": "Cement & Building Materials"},
    {"ticker": "HUDCO.NS", "symbol": "HUDCO", "name": "Housing & Urban Dev Corp Ltd", "aliases": ["HUDCO", "Housing Finance", "Infra PSU"], "sector": "Financial Services (PSU)"},
    {"ticker": "NHPC.NS", "symbol": "NHPC", "name": "NHPC Ltd", "aliases": ["NHPC", "Hydro Power", "Green Energy"], "sector": "Power & Utilities"},
    {"ticker": "PFC.NS", "symbol": "PFC", "name": "Power Finance Corporation Ltd", "aliases": ["PFC", "Power Finance", "PSU Finance"], "sector": "Financial Services (PSU)"},
    {"ticker": "RECLTD.NS", "symbol": "RECLTD", "name": "REC Ltd", "aliases": ["REC", "Rural Electrification", "PSU Finance"], "sector": "Financial Services (PSU)"},
    {"ticker": "JINDALSTEL.NS", "symbol": "JINDALSTEL", "name": "Jindal Steel & Power Ltd", "aliases": ["Jindal Steel", "JSPL", "Naveen Jindal"], "sector": "Metals & Mining"},
    {"ticker": "NMDC.NS", "symbol": "NMDC", "name": "NMDC Ltd", "aliases": ["NMDC", "Iron Ore Mining", "Mining PSU"], "sector": "Metals & Mining"},
    {"ticker": "SAIL.NS", "symbol": "SAIL", "name": "Steel Authority of India Ltd", "aliases": ["SAIL", "Steel PSU"], "sector": "Metals & Mining"},
    {"ticker": "MRF.NS", "symbol": "MRF", "name": "MRF Ltd", "aliases": ["MRF", "Madras Rubber Factory", "Tyres"], "sector": "Automobile Tyres"},
    {"ticker": "APOLLOTYRE.NS", "symbol": "APOLLOTYRE", "name": "Apollo Tyres Ltd", "aliases": ["Apollo Tyres", "Apollo Tyre"], "sector": "Automobile Tyres"},
    {"ticker": "EXIDEIND.NS", "symbol": "EXIDEIND", "name": "Exide Industries Ltd", "aliases": ["Exide", "Exide Batteries", "EV Battery"], "sector": "Automobile Ancillary"},
    {"ticker": "BOSCHLTD.NS", "symbol": "BOSCHLTD", "name": "Bosch Ltd", "aliases": ["Bosch", "Auto Components"], "sector": "Automobile Ancillary"},
    {"ticker": "BIOCON.NS", "symbol": "BIOCON", "name": "Biocon Ltd", "aliases": ["Biocon", "Kiran Mazumdar Shaw", "Biosimilars"], "sector": "Pharmaceuticals"},
    {"ticker": "LUPIN.NS", "symbol": "LUPIN", "name": "Lupin Ltd", "aliases": ["Lupin", "Pharma"], "sector": "Pharmaceuticals"},
    {"ticker": "AUROPHARMA.NS", "symbol": "AUROPHARMA", "name": "Aurobindo Pharma Ltd", "aliases": ["Aurobindo", "Aurobindo Pharma"], "sector": "Pharmaceuticals"},
    {"ticker": "PERSISTENT.NS", "symbol": "PERSISTENT", "name": "Persistent Systems Ltd", "aliases": ["Persistent", "Persistent Systems", "IT Services"], "sector": "Information Technology"},
    {"ticker": "COFORGE.NS", "symbol": "COFORGE", "name": "Coforge Ltd", "aliases": ["Coforge", "NIIT Tech"], "sector": "Information Technology"},
    {"ticker": "KPITTECH.NS", "symbol": "KPITTECH", "name": "KPIT Technologies Ltd", "aliases": ["KPIT", "KPIT Tech", "Automotive Software"], "sector": "Information Technology"},
    {"ticker": "TATAELXSI.NS", "symbol": "TATAELXSI", "name": "Tata Elxsi Ltd", "aliases": ["Tata Elxsi", "Elxsi", "Design & Tech"], "sector": "Information Technology"},
    {"ticker": "BSE.NS", "symbol": "BSE", "name": "BSE Ltd", "aliases": ["BSE", "Bombay Stock Exchange", "Exchange"], "sector": "Capital Markets"},
    {"ticker": "MCX.NS", "symbol": "MCX", "name": "Multi Commodity Exchange of India Ltd", "aliases": ["MCX", "Commodity Exchange", "Gold Silver"], "sector": "Capital Markets"},
    {"ticker": "CDSL.NS", "symbol": "CDSL", "name": "Central Depository Services (India) Ltd", "aliases": ["CDSL", "Depository", "Demat Account"], "sector": "Capital Markets"},

    # Additional Liquid NSE Equities (Indic-Finance & Broad Coverage)
    {"ticker": "ACC.NS", "symbol": "ACC", "name": "ACC Ltd", "aliases": ["ACC", "Associated Cement", "Adani Cement"], "sector": "Cement & Building Materials"},
    {"ticker": "ADANIGREEN.NS", "symbol": "ADANIGREEN", "name": "Adani Green Energy Ltd", "aliases": ["Adani Green", "AGEL", "Solar", "Wind Energy"], "sector": "Power & Renewable Energy"},
    {"ticker": "ADANIPOWER.NS", "symbol": "ADANIPOWER", "name": "Adani Power Ltd", "aliases": ["Adani Power", "Thermal Power", "APL"], "sector": "Power & Utilities"},
    {"ticker": "ATGL.NS", "symbol": "ATGL", "name": "Adani Total Gas Ltd", "aliases": ["Adani Total Gas", "City Gas", "PNG", "CNG"], "sector": "Energy & Utilities"},
    {"ticker": "AUBANK.NS", "symbol": "AUBANK", "name": "AU Small Finance Bank Ltd", "aliases": ["AU Bank", "AU Small Finance", "SFB"], "sector": "Banking & Finance"},
    {"ticker": "AWL.NS", "symbol": "AWL", "name": "Adani Wilmar Ltd", "aliases": ["Adani Wilmar", "Fortune Oil", "Edible Oil", "Wilmar"], "sector": "Consumer Goods (FMCG)"},
    {"ticker": "BANDHANBNK.NS", "symbol": "BANDHANBNK", "name": "Bandhan Bank Ltd", "aliases": ["Bandhan", "Bandhan Bank", "Microfinance"], "sector": "Banking & Finance"},
    {"ticker": "CGPOWER.NS", "symbol": "CGPOWER", "name": "CG Power and Industrial Solutions Ltd", "aliases": ["CG Power", "Crompton Greaves", "Murugappa"], "sector": "Capital Goods & Electricals"},
    {"ticker": "CHOLAFIN.NS", "symbol": "CHOLAFIN", "name": "Cholamandalam Investment and Finance Co Ltd", "aliases": ["Cholamandalam", "Chola", "Vehicle Finance"], "sector": "Banking & Finance"},
    {"ticker": "COLPAL.NS", "symbol": "COLPAL", "name": "Colgate-Palmolive (India) Ltd", "aliases": ["Colgate", "Palmolive", "Oral Care"], "sector": "Consumer Goods (FMCG)"},
    {"ticker": "DIXON.NS", "symbol": "DIXON", "name": "Dixon Technologies (India) Ltd", "aliases": ["Dixon", "Dixon Tech", "EMS", "Electronics"], "sector": "Consumer Discretionary"},
    {"ticker": "GODREJPROP.NS", "symbol": "GODREJPROP", "name": "Godrej Properties Ltd", "aliases": ["Godrej Properties", "GPL", "Godrej Real Estate"], "sector": "Real Estate"},
    {"ticker": "INDHOTEL.NS", "symbol": "INDHOTEL", "name": "The Indian Hotels Company Ltd", "aliases": ["Indian Hotels", "IHCL", "Taj Hotels", "Vivanta", "Ginger"], "sector": "Hospitality & Tourism"},
    {"ticker": "KEI.NS", "symbol": "KEI", "name": "KEI Industries Ltd", "aliases": ["KEI", "KEI Wires", "Cables"], "sector": "Capital Goods & Cables"},
    {"ticker": "LICI.NS", "symbol": "LICI", "name": "Life Insurance Corporation of India", "aliases": ["LIC", "LICI", "Life Insurance"], "sector": "Insurance & Finance"},
    {"ticker": "MACROTECH.NS", "symbol": "MACROTECH", "name": "Macrotech Developers Ltd", "aliases": ["Lodha", "Macrotech", "Lodha Group"], "sector": "Real Estate"},
    {"ticker": "MANAPPURAM.NS", "symbol": "MANAPPURAM", "name": "Manappuram Finance Ltd", "aliases": ["Manappuram", "Gold Loan", "Manappuram Finance"], "sector": "Banking & Finance"},
    {"ticker": "MOTHERSUMI.NS", "symbol": "MOTHERSUMI", "name": "Samvardhana Motherson International Ltd", "aliases": ["Motherson", "Motherson Sumi", "Auto Ancillary", "Wiring Harness"], "sector": "Automobile Ancillary"},
    {"ticker": "MPHASIS.NS", "symbol": "MPHASIS", "name": "Mphasis Ltd", "aliases": ["Mphasis", "Mphasis IT", "BPO"], "sector": "Information Technology"},
    {"ticker": "MUTHOOTFIN.NS", "symbol": "MUTHOOTFIN", "name": "Muthoot Finance Ltd", "aliases": ["Muthoot", "Muthoot Gold", "Gold Loans"], "sector": "Banking & Finance"},
    {"ticker": "NDTV.NS", "symbol": "NDTV", "name": "New Delhi Television Ltd", "aliases": ["NDTV", "New Delhi Television", "Adani Media", "News Channel"], "sector": "Media & Entertainment"},
    {"ticker": "OBEROIRLTY.NS", "symbol": "OBEROIRLTY", "name": "Oberoi Realty Ltd", "aliases": ["Oberoi", "Oberoi Realty", "Luxury Housing"], "sector": "Real Estate"},
    {"ticker": "PIIND.NS", "symbol": "PIIND", "name": "PI Industries Ltd", "aliases": ["PI Industries", "Agrochemicals", "CSM"], "sector": "Chemicals & Agri"},
    {"ticker": "SBICARD.NS", "symbol": "SBICARD", "name": "SBI Cards and Payment Services Ltd", "aliases": ["SBI Card", "Credit Card", "SBI Cards"], "sector": "Banking & Finance"},
    {"ticker": "SPICEJET.NS", "symbol": "SPICEJET", "name": "SpiceJet Ltd", "aliases": ["SpiceJet", "Airline", "Aviation"], "sector": "Aviation & Airlines"},
    {"ticker": "SRF.NS", "symbol": "SRF", "name": "SRF Ltd", "aliases": ["SRF", "Specialty Chemicals", "Packaging Films"], "sector": "Chemicals & Materials"},
    {"ticker": "TATATECH.NS", "symbol": "TATATECH", "name": "Tata Technologies Ltd", "aliases": ["Tata Tech", "Tata Technologies", "ER&D"], "sector": "Information Technology"},
    {"ticker": "TORNTPHARM.NS", "symbol": "TORNTPHARM", "name": "Torrent Pharmaceuticals Ltd", "aliases": ["Torrent Pharma", "Torrent"], "sector": "Pharmaceuticals"},
]


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Standard Levenshtein edit distance for typo tolerance."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev[j + 1] + 1
            deletions = curr[j] + 1
            substitutions = prev[j] + (c1 != c2)
            curr.append(min(insertions, deletions, substitutions))
        prev = curr
    return prev[-1]


class IndianStockMasterIndex:
    """
    In-memory searchable index for all Indian listed companies.
    Supports partial prefix, substring, alias, and typo-tolerant matching.
    """

    def __init__(self):
        self.stocks = INDIAN_STOCKS_DATA
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 90  # 90 seconds cache per quote

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            # Return top default Indian benchmarks and blue chips
            defaults = ["^NSEI", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATAMOTORS.NS"]
            return [s for s in self.stocks if s["ticker"] in defaults][:limit]

        q = query.strip().lower()
        q_clean = re.sub(r'[^a-z0-9]', '', q)

        STOPWORDS = {'ltd', 'limited', 'share', 'shares', 'stock', 'stocks', 'corp', 'corporation', 'co', 'company', 'india', 'pvt', 'inc'}
        q_tokens = [w for w in re.findall(r'[a-z0-9]+', q) if w not in STOPWORDS]

        exact_matches = []
        prefix_matches = []
        token_matches = []
        substring_matches = []
        fuzzy_matches = []

        seen_tickers = set()

        for s in self.stocks:
            ticker = s["ticker"]
            symbol = s["symbol"].lower()
            name = s["name"].lower()
            aliases = [a.lower() for a in s.get("aliases", [])]

            # 1. Exact match on ticker or symbol
            if q == symbol or q == ticker.lower() or q == symbol.replace('.ns', ''):
                exact_matches.append(s)
                seen_tickers.add(ticker)
                continue

            # 2. Prefix match on symbol, ticker, or aliases
            if symbol.startswith(q) or any(a.startswith(q) for a in aliases) or name.startswith(q):
                prefix_matches.append(s)
                seen_tickers.add(ticker)
                continue

            # 3. Multi-token match (e.g. 'hero motors ltd' -> 'hero' & 'motors')
            if len(q_tokens) >= 1:
                searchable_text = f"{symbol} {name} {' '.join(aliases)} {s.get('sector', '').lower()}"
                if all(tok in searchable_text for tok in q_tokens):
                    token_matches.append(s)
                    seen_tickers.add(ticker)
                    continue

            # 4. Substring match in name, aliases, or sector
            if q in name or any(q in a for a in aliases) or (len(q) >= 3 and q in s.get("sector", "").lower()):
                substring_matches.append(s)
                seen_tickers.add(ticker)
                continue

            # 5. Fuzzy typo tolerance (if query length >= 4)
            if len(q_clean) >= 4 and ticker not in seen_tickers:
                words = re.findall(r'[a-z0-9]+', name) + [symbol] + [re.sub(r'[^a-z0-9]', '', a) for a in aliases]
                min_dist = min([_levenshtein_distance(q_clean, w) for w in words if len(w) >= 3] or [99])
                max_allowed = 1 if len(q_clean) <= 6 else 2
                if min_dist <= max_allowed:
                    fuzzy_matches.append((min_dist, s))
                    seen_tickers.add(ticker)

        # Sort fuzzy matches by edit distance
        fuzzy_matches.sort(key=lambda x: x[0])
        sorted_fuzzy = [item[1] for item in fuzzy_matches]

        combined = exact_matches + prefix_matches + token_matches + substring_matches + sorted_fuzzy

        # 6. Dynamic Online Fallback via Yahoo Finance for any other Indian stock not yet indexed
        if len(combined) < 3 and len(q_clean) >= 3:
            try:
                import urllib.request
                import urllib.parse
                import json
                clean_search = ' '.join(q_tokens) if q_tokens else query.strip()
                url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(clean_search)}&quotesCount=6"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                res = json.loads(urllib.request.urlopen(req, timeout=2.5).read())
                for item in res.get("quotes", []):
                    sym = (item.get("symbol") or "").upper()
                    if (sym.endswith(".NS") or sym.endswith(".BO")) and sym not in seen_tickers:
                        raw_name = item.get("shortname") or item.get("longname") or sym
                        clean_sym = sym.replace(".NS", "").replace(".BO", "")
                        online_stock = {
                            "ticker": sym,
                            "symbol": clean_sym,
                            "name": raw_name,
                            "aliases": [clean_sym, raw_name],
                            "sector": item.get("sector") or "Indian Equities"
                        }
                        combined.append(online_stock)
                        seen_tickers.add(sym)
                        if not any(st["ticker"] == sym for st in self.stocks):
                            self.stocks.append(online_stock)
            except Exception:
                pass

        return combined[:limit]

    def _get_fallback_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fallback to database market_cache or stock_price table if provider is throttled or offline."""
        try:
            from database import get_connection
            conn = get_connection()
            mc = conn.execute("SELECT price, change_pct FROM market_cache WHERE ticker=?", (ticker,)).fetchone()
            if mc and mc["price"] is not None:
                conn.close()
                p = float(mc["price"])
                cp = float(mc["change_pct"] or 0.0)
                ca = round(p * (cp / 100), 2)
                return {"price": p, "change_amount": ca, "change_pct": cp}

            rows = conn.execute("SELECT close FROM stock_price WHERE ticker=? ORDER BY date DESC LIMIT 2", (ticker,)).fetchall()
            conn.close()
            if rows and len(rows) >= 1:
                p = float(rows[0]["close"])
                prev = float(rows[1]["close"]) if len(rows) > 1 else p
                ca = round(p - prev, 2)
                cp = round((ca / prev) * 100, 2) if prev else 0.0
                return {"price": p, "change_amount": ca, "change_pct": cp}
        except Exception:
            pass

        # Static baseline anchor for top stocks if provider is offline
        anchor_prices = {
            "TATAMOTORS.NS": {"price": 968.40, "change_amount": 8.50, "change_pct": 0.89},
            "^NSEI": {"price": 25795.10, "change_amount": 142.30, "change_pct": 0.56},
            "^BSESN": {"price": 84266.30, "change_amount": 420.50, "change_pct": 0.50},
        }
        return anchor_prices.get(ticker)

    def enrich_with_quotes(self, matches: List[Dict[str, Any]], market_aggregator) -> List[Dict[str, Any]]:
        """
        Enriches matched stocks with live/cached last-traded price (₹) and day change.
        Guarantees fast response times by checking memory cache and local DB before remote calls.
        """
        now = time.time()
        enriched = []

        for item in matches:
            ticker = item["ticker"]
            cached = self._price_cache.get(ticker)

            if cached and (now - cached["timestamp"] < self._cache_ttl):
                quote_data = cached["data"]
            else:
                try:
                    quote_data = market_aggregator.get_quote(ticker)
                    if not quote_data or quote_data.get("price") is None:
                        fallback = self._get_fallback_quote(ticker)
                        if fallback:
                            quote_data = {
                                "price": fallback["price"],
                                "change_amount": fallback["change_amount"],
                                "change_pct": fallback["change_pct"],
                                "status": "cached",
                            }
                    self._price_cache[ticker] = {"timestamp": now, "data": quote_data}
                except Exception:
                    fallback = self._get_fallback_quote(ticker)
                    quote_data = fallback or {}

            price = quote_data.get("price") if quote_data else None
            change_amount = quote_data.get("change_amount", 0.0) if quote_data else 0.0
            change_pct = quote_data.get("change_pct", 0.0) if quote_data else 0.0

            # Format price and change nicely in INR (₹)
            is_index = ticker.startswith("^")
            currency_symbol = "" if is_index else "\u20b9"
            
            formatted_price = f"{currency_symbol}{price:,.2f}" if price is not None else "Price N/A"
            sign = "+" if change_amount > 0 else ""
            formatted_change = f"{sign}{currency_symbol}{change_amount:,.2f} ({sign}{change_pct:.2f}%)" if price is not None else "\u2014"

            enriched.append({
                "ticker": ticker,
                "symbol": item["symbol"],
                "name": item["name"],
                "sector": item["sector"],
                "price": price,
                "change_amount": change_amount,
                "change_pct": change_pct,
                "formatted_price": formatted_price,
                "formatted_change": formatted_change,
                "direction": "UP" if change_pct > 0 else ("DOWN" if change_pct < 0 else "NEUTRAL"),
                "is_index": is_index
            })

        return enriched


# Global Singleton Instance
stock_master_index = IndianStockMasterIndex()
