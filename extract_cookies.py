import browser_cookie3
import http.cookiejar

# Choose your browser (chrome, firefox, opera, edge)
cookies = browser_cookie3.chrome(domain_name='.youtube.com')

# Save cookies to file
with open('youtube_cookies.txt', 'w') as f:
    for cookie in cookies:
        if cookie.domain.endswith('.youtube.com') or cookie.domain.endswith('.google.com'):
            f.write(f"{cookie.domain}\tTRUE\t{cookie.path}\t{cookie.secure}\t{cookie.expires}\t{cookie.name}\t{cookie.value}\n")

print("Cookies extracted and saved to youtube_cookies.txt")
