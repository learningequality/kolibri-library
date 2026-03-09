index.py  # crawl from website to jsonlines -- jsonlines may require deduplication
  full.uniq.jsonlines is output | sort | uniq
process.py # jsonlines to tagcounter
tags.py # tagcounter as python -- hand edited output of process.py
tagnest.py # output tagcounter in sortable form
