import csv

cfx_data = []
for i in range(1,4):
    with open(f'cfx-data{i}.csv', newline='') as File:  
        reader = csv.reader(File, delimiter='\t')
        for row in reader:
            try:
                row[0] = 200000 * (i-1) + int(row[0])
                cfx_data.append(row)
            except:
                pass
cfx_data.sort(key=lambda x: x[0])
print(len(cfx_data))

with open('cfx-data.csv', 'w', newline='') as csvfile:
    spamwriter = csv.writer(csvfile, delimiter='\t')
    for row in cfx_data:
        spamwriter.writerow(row)

