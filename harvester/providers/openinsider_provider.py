import pandas as pd

# 1. Go to OpenInsider, run your screen, and copy the URL.
# Here is an example URL for all CEO purchases:
url = 'http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=730&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&isofficer=1&iscob=1&isceo=1&ispres=1&iscoo=1&iscfo=1&isgc=1&isvp=1&isdirector=1&istenpercent=1&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=1000&page=1'

# 2. Use Pandas to read the HTML table directly from the URL
tables = pd.read_html(url)

# 3. OpenInsider's main data table is usually the 11th table on the page (index 11),
# but it can sometimes be index 12 depending on the page structure.
df = tables[11]

# Display the data
print(df.head())

# Save it to your own CSV
df.to_csv("openinsider_data.csv", index=False)