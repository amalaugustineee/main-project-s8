"""
Diagnostic script to test PubMed lookup with detailed logging
"""
import requests
import json

NCBI_ESearch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_ESummary = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

def fetch_pubmed_articles_debug(test_name, retmax=2):
    """
    Debug version with verbose logging
    """
    print(f"\n{'='*60}")
    print(f"🔍 Testing PubMed lookup for: {test_name}")
    print(f"{'='*60}")
    
    # Step 1: Search for article IDs
    search_term = f"{test_name} health risk meta-analysis"
    print(f"\n1️⃣ ESearch query: '{search_term}'")
    
    params = {
        "db": "pubmed",
        "term": search_term,
        "retmode": "json",
        "retmax": retmax
    }
    
    try:
        r = requests.get(NCBI_ESearch, params=params, timeout=20)
        print(f"   Status: {r.status_code}")
        
        if r.status_code != 200:
            print(f"   ❌ Error: HTTP {r.status_code}")
            print(f"   Response: {r.text[:500]}")
            return []
            
        search_result = r.json()
        ids = search_result.get("esearchresult", {}).get("idlist", [])
        count = search_result.get("esearchresult", {}).get("count", 0)
        
        print(f"   Total results: {count}")
        print(f"   Retrieved IDs: {ids}")
        
        if not ids:
            print(f"   ⚠️ No PubMed IDs found for this search term")
            return []
            
    except Exception as e:
        print(f"   ❌ ESearch failed: {e}")
        return []
    
    # Step 2: Fetch article summaries
    print(f"\n2️⃣ ESummary query for IDs: {ids}")
    
    params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
    
    try:
        r = requests.get(NCBI_ESummary, params=params, timeout=20)
        print(f"   Status: {r.status_code}")
        
        if r.status_code != 200:
            print(f"   ❌ Error: HTTP {r.status_code}")
            return []
            
        summary_data = r.json()
        summaries = []
        
        for pid in ids:
            info = summary_data.get("result", {}).get(pid)
            if info:
                article = {
                    "title": info.get("title"),
                    "source": info.get("source"),
                    "pubdate": info.get("pubdate"),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"
                }
                summaries.append(article)
                print(f"\n   📄 Article {pid}:")
                print(f"      Title: {article['title'][:80]}...")
                print(f"      Source: {article['source']}")
                print(f"      Date: {article['pubdate']}")
            else:
                print(f"   ⚠️ No data for ID {pid}")
        
        print(f"\n✅ Successfully retrieved {len(summaries)} articles")
        return summaries
        
    except Exception as e:
        print(f"   ❌ ESummary failed: {e}")
        return []


if __name__ == "__main__":
    # Test with the same test name from your screenshot
    test_names = [
        "HCT (HEMATOCRIT)",
        "Hemoglobin",
        "Cholesterol LDL"
    ]
    
    for test in test_names:
        results = fetch_pubmed_articles_debug(test, retmax=2)
        print(f"\n📊 Final result: {len(results)} articles\n")
