from bs4 import BeautifulSoup as bs
from concurrent.futures import ThreadPoolExecutor as PoolExecutor
import requests
import pandas as pd
import time

# Returns the page
def fetch_res(url):
    return requests.get(url)

# Url structure: root_url + numpages
root_url = "https://news.ycombinator.com/news?p="
numpages = 25
hds, links = [], []

# Generate links for us to fetch
for i in range(1,numpages+1):
    links.append(root_url+str(i))

# Timing loop for just request fetching and parsing.
start_time = time.time()

with PoolExecutor(max_workers=4) as executor:
    for page in executor.map(fetch_res, links):
        parsed = bs(page.content, 'html.parser')
        headlines = parsed.find_all('a', class_='storylink')
        scores = parsed.find_all('span', class_='score')
        sitestr = parsed.find_all('span', class_='sitestr')

        for a,b,c in zip(headlines, scores, sitestr):
            hds.append([a.get_text(), int(b.get_text().split()[0]), c.get_text()])

print(time.time()-start_time,"seconds")

df = pd.DataFrame(hds)
df.columns = ['Title', 'Score', 'Site']
print(df.head(10))