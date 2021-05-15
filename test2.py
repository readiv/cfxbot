import csv
with open("ports.csv", 'w', newline='') as csvfile:
    csvwriter = csv.writer(csvfile, delimiter=',')
    for i in range(65536):
        csvwriter.writerow([i])