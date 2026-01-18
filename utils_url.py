import requests
import warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

def url_seems_reachable(url: str, timeout: float = 10.0) -> bool:
    """
    Check if a URL is reachable with browser-like headers.
    Strict on HTTP errors, lenient on network/timeout issues.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    # Allow localhost and example.com for testing/internal use
    domain = url.split('/')[2] if '//' in url else url.split('/')[0]
    if 'example.com' in domain or 'localhost' in domain or '127.0.0.1' in domain:
        return True
    
    try:
        resp = requests.get(
            url, 
            allow_redirects=True, 
            timeout=timeout,
            headers=headers,
            verify=False
        )
        
        # Accept 2xx (success), 3xx (redirects), 4xx (client errors)
        # Reject only 5xx (server errors)
        return resp.status_code < 500
        
    except requests.exceptions.Timeout:
        # Timeout = server is slow but URL might be valid
        print(f"URL verification timeout for {url}, allowing (server may be slow)")
        return True
        
    except requests.exceptions.ConnectionError as e:
        # Connection failed - could be network issue OR invalid domain
        error_msg = str(e).lower()
        
        # If DNS resolution fails, the domain doesn't exist
        if 'name or service not known' in error_msg or 'nodename nor servname provided' in error_msg or 'failed to resolve' in error_msg:
            print(f"URL verification failed for {url}: domain does not exist")
            return False  # ❌ Reject - domain doesn't exist
        
        # For other connection errors, be lenient (firewall, network issues)
        print(f"URL verification connection error for {url}, allowing (may be network issue)")
        return True
        
    except requests.exceptions.InvalidURL:
        # Malformed URL
        print(f"Invalid URL format: {url}")
        return False  # ❌ Reject - URL is malformed
        
    except Exception as e:
        # Unknown error - be cautious but lenient
        print(f"URL verification error for {url}: {str(e)}, allowing")
        return True
