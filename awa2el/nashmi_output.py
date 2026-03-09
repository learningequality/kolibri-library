import index
import csv

with open('nashmi.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(["URL", "top", "middle", "lower", "url"])

    for item in index.get_lectures():
        print ('\t'.join([str(x) for x in item]))
        writer.writerow(item)

