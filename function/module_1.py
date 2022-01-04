#! /usr/bin/env python3

## import modules
from Bio import Entrez
from Bio.SeqIO import FastaIO 
from tqdm import tqdm
from urllib.error import HTTPError
import time
from Bio import SeqIO
from Bio.Seq import Seq
import subprocess as sp
import os
from string import digits
import codecs


## functions NCBI
def wget_ncbi(query, database, email, batchsize, output):
    print('looking up the number of sequences that match the query')
    url_esearch = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db={database}&usehistory=y&email={email}&term={query}'
    result = sp.run(['wget', url_esearch, '-O', 'esearch_output.txt'], stdout = sp.DEVNULL, stderr = sp.DEVNULL)
    with open('esearch_output.txt', 'r') as file_in:
        for line in file_in:
            if line.startswith('<eSearchResult>'):
                seqcount = line.split('Count>')[1].rstrip('</')
                print(f'found {seqcount} number of sequences matching the query')
                print('starting the download')
                querykey = line.split('QueryKey>')[1].rstrip('</')
                webenv = line.split('WebEnv>')[1].rstrip('</')
    
    count = 0
    for i in range(0, int(seqcount), batchsize):
        count = count+1
        url2 = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db={database}&email={email}&query_key={querykey}&WebEnv={webenv}&rettype=fasta&retstart={i}&retmax={batchsize}'
        results = sp.run(['wget', url2, '-O', f'temp_{output}_{count}.fasta',  '-q', '--show-progress'])

    tempfiles = [f for f in os.listdir() if f.startswith(f'temp_{output}_')]
    with open('CRABS_ncbi_download.fasta', 'a') as file_out:
        for tempfile in tempfiles:
            with open(tempfile, 'r') as infile:
                for line in infile:
                    file_out.write(line)

    os.remove('esearch_output.txt')
    for tempfile in tempfiles:
        os.remove(tempfile)

def esearch_fasta(query, database, email):
    Entrez.email = email
    first_handle = Entrez.esearch(db=database, term=query, rettype='fasta')
    first_record = Entrez.read(first_handle)
    first_handle.close()
    count = int(first_record['Count'])
    # now, second round from first
    second_handle = Entrez.esearch(db=database, term=query, retmax=count, rettype='fasta', usehistory = 'y')
    second_record = Entrez.read(second_handle)
    second_handle.close()
    return second_record

def efetch_seqs_from_webenv(web_record, database, email, batch_size, output):
    Entrez.email = email
    id_list = web_record['IdList']
    count = int(web_record['Count'])
    assert(count == len(id_list))
    webenv = web_record['WebEnv']
    query_key = web_record['QueryKey']

    out_handle = open(output, 'w')
    for start in tqdm(range(0, count, batch_size)):
        attempt = 1
        success = False
        while attempt <= 3 and not success:
            attempt += 1
            try:
                fetch_handle = Entrez.efetch(db=database, rettype='fasta',
                                            retstart=start, retmax=batch_size,
                                            webenv=webenv, query_key=query_key)
                success = True
            except HTTPError as err:
                if 500 <= err.code <= 599:
                    print(f"Received error from server {err}")
                    print("Attempt {attempt} of 3")
                    time.sleep(15)
                else:
                    raise
        data = fetch_handle.read()
        fetch_handle.close()
        out_handle.write(data)
    out_handle.close()
    numseq = len(list(SeqIO.parse(output, 'fasta')))

    return numseq

def ncbi_formatting(file, original, discard):
    mistakes = ['@', '#', '$', '%', '&', '(', ')', '!', '<', '?', '|', ',', '.', '+', '=', '`', '~']
    newfile = []
    discarded = []
    with tqdm(total = os.path.getsize('CRABS_ncbi_download.fasta')) as pbar:
        for record in SeqIO.parse('CRABS_ncbi_download.fasta', 'fasta'):
            pbar.update(len(record))
            acc = str(record.description.split('.')[0])
            if not any(mistake in acc for mistake in mistakes):
                record.description = acc
                record.id = record.description
                newfile.append(record)
            else:
                discarded.append(record)
        newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
        with open(file, 'w') as fout:
            for item in newfile_db:
                fout.write(item)
        if discard != 'no':
            discarded_db = [FastaIO.as_fasta_2line(record) for record in discarded]
            with open(discard, 'w') as fbad:
                for item in discarded_db:
                    fbad.write(item)
    print(f'found {len(discarded)} sequences with incorrect accession format')
    if original != 'yes':
        os.remove('CRABS_ncbi_download.fasta')
    numseq = len(newfile)

    return numseq

## functions MitoFish
def mitofish_download(website):
    results = sp.run(['wget', website, '-q', '--show-progress'])
    results = sp.run(['unzip', 'complete_partial_mitogenomes.zip'], stdout = sp.DEVNULL, stderr = sp.DEVNULL)
    fasta = 'complete_partial_mitogenomes.fa'
    os.remove('complete_partial_mitogenomes.zip')

    return fasta

def mitofish_format(file_in, file_out, original, discard):
    mistakes = ['@', '#', '$', '%', '&', '(', ')', '!', '<', '?', '|', ',', '.', '+', '=', '`', '~']
    newfile = []
    discarded = []
    with tqdm(total = os.path.getsize(file_in)) as pbar:
        for record in SeqIO.parse(file_in, 'fasta'):
            pbar.update(len(record))
            acc = str(record.description.split('|')[1])
            if acc.isdigit():
                acc = str(record.description.split('|')[3])
            if not any(mistake in acc for mistake in mistakes):
                record.description = acc
                record.id = record.description
                newfile.append(record)
            else:
                discarded.append(record)
    newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
    with open(file_out, 'w') as fout:
        for item in newfile_db:
            fout.write(item)
    if discard != 'no':
        discarded_db = [FastaIO.as_fasta_2line(record) for record in discarded]
        with open(discard, 'w') as fbad:
            for item in discarded_db:
                fbad.write(item)
    print(f'found {len(discarded)} sequences with incorrect accession format')
    numseq = len(newfile)
    if original != 'yes':
        os.remove(file_in)

    return numseq

## functions EMBL
def embl_download(database):
    url = 'ftp://ftp.ebi.ac.uk/pub/databases/embl/release/std/rel_std_' + database
    result = sp.run(['wget', url, '-q', '--show-progress'])
    gfiles = [f for f in os.listdir() if f.startswith('rel_std')]
    ufiles = []
    for gfile in gfiles:
        unzip = gfile[:-3]
        ufiles.append(unzip)
        print(f'unzipping file: {unzip}')
        results = sp.run(['gunzip', gfile])
    
    return ufiles

def embl_fasta_format(dat_format):
    ffiles = []
    for ufile in dat_format:
        ffile = ufile[:-4] + '.fasta'
        ffiles.append(ffile)
        fasta = []
        seq_len = []
        count = 0
        print(f'formatting {ufile} to fasta format')
        with tqdm(total = os.path.getsize(ufile)) as pbar:
            with open(ufile, 'r') as file:
                for line in file:
                    pbar.update(len(line))
                    if line.startswith('AC'):
                        part = '>' + line.split('   ')[1].split(';')[0]
                    elif line.startswith('     '):
                        remove_digits = str.maketrans('', '', digits)
                        seq = line.replace(' ', '').translate(remove_digits).upper().rstrip('\n')
                        seq_len.append(seq)
                        count = count + 1
                    elif line.startswith('//'):
                        if count < 900:
                            fasta.append(part)
                            for item in seq_len:
                                fasta.append(item)
                            seq_len = []
                            count = 0
                        else:
                            seq_len = []
                            count = 0
        with open(ffile, 'w') as fa:
            print(f'saving {ffile}')
            for element in fasta:
                fa.write('{}\n'.format(element))
    #for ufile in dat_format:
        os.remove(ufile)
    intermediary_file = 'CRABS_embl_download.fasta'
    print('Combining all EMBL downloaded fasta files...')
    with open(intermediary_file, 'w') as w_file:
        for filen in ffiles:
            with open(filen, 'rU') as o_file:
                seq_records = SeqIO.parse(o_file, 'fasta')
                SeqIO.write(seq_records, w_file, 'fasta')
    for f in ffiles:
        os.remove(f)
    return intermediary_file

def embl_crabs_format(f_in, f_out, original, discard):
    mistakes = ['@', '#', '$', '%', '&', '(', ')', '!', '<', '?', '|', ',', '.', '+', '=', '`', '~']
    newfile = []
    discarded = []
    with tqdm(total = os.path.getsize(f_in)) as pbar:
        for record in SeqIO.parse(f_in, 'fasta'):
            pbar.update(len(record))
            acc = str(record.id)
            if not any(mistake in acc for mistake in mistakes):
                record.description = acc
                record.id = record.description
                newfile.append(record)
            else:
                discarded.append(record)
    newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
    with open(f_out, 'w') as fout:
        for item in newfile_db:
            fout.write(item)
    if discard != 'no':
        discarded_db = [FastaIO.as_fasta_2line(record) for record in discarded]
        with open(discard, 'w') as fbad:
            for item in discarded_db:
                fbad.write(item)
    print(f'found {len(discarded)} sequences with incorrect accession format')
    numseq = len(newfile)
    if original != 'yes':
        os.remove(f_in)

    return numseq

## functions BOLD
def bold_download(entry):
    url = 'http://v3.boldsystems.org/index.php/API_Public/sequence?taxon=' + entry 
    filename = 'CRABS_bold_download.fasta'
    result = sp.run(['wget', url, '-O', filename, '-q', '--show-progress'])
    BLOCKSIZE = 1048576
    with codecs.open(filename, 'r', 'latin1') as sourcefile:
        with codecs.open('mid.fasta', 'w', 'utf-8') as targetfile:
            while True:
                contents = sourcefile.read(BLOCKSIZE)
                if not contents:
                    break
                targetfile.write(contents)
    results = sp.run(['mv', 'mid.fasta', filename])
    num_bold = len(list(SeqIO.parse(filename, 'fasta')))
    
    return num_bold

def bold_format(f_out, original, discard):
    mistakes = ['@', '#', '$', '%', '&', '(', ')', '!', '<', '?', '|', ',', '.', '+', '=', '`', '~']
    newfile = []
    discarded = []
    count = 0
    with tqdm(total = os.path.getsize('CRABS_bold_download.fasta')) as pbar:
        for record in SeqIO.parse('CRABS_bold_download.fasta', 'fasta'):
            pbar.update(len(record))
            if record.description.split('-')[-1] == 'SUPPRESSED':
                discarded.append(record)
            else:
                if len(record.description.split('|')) == 4:
                    acc = str(record.description.split('|')[3].split('.')[0])
                    if not any(mistake in acc for mistake in mistakes):
                        record.description = acc
                        record.id = record.description
                        record.seq = record.seq.strip('-')
                        if record.seq.count('-') == 0:
                            newfile.append(record)
                    else:
                        discarded.append(record)
                else:
                    count = count +1
                    spec = str(record.description.split('|')[1].replace(' ', '_'))
                    acc_crab = 'CRABS_' + str(count) + ':' + spec 
                    record.description = acc_crab
                    record.id = record.description
                    record.name = record.description
                    record.seq = record.seq.strip('-')
                    if record.seq.count('-') == 0:
                        newfile.append(record)
    newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
    with open(f_out, 'w') as fout:
        for item in newfile_db:
            fout.write(item)
    if discard != 'no':
        discarded_db = [FastaIO.as_fasta_2line(record) for record in discarded]
        with open(discard, 'w') as fbad:
            for item in discarded_db:
                fbad.write(item)
    print(f'found {len(discarded)} sequences with incorrect accession format')
    numseq = len(newfile)
    if original != 'yes':
        os.remove('CRABS_bold_download.fasta')

    return numseq


## function: import
def check_accession(file_in, file_out, delimiter):
    mistakes = ['@', '#', '$', '%', '&', '(', ')', '!', '<', '?', '|', ',', '.', '+', '=', '`', '~']
    newfile = []
    discarded = []
    for record in SeqIO.parse(file_in, 'fasta'):
        acc = str(record.description.split(delimiter)[0])
        if not any(mistake in acc for mistake in mistakes):
            record.description = acc 
            record.id = record.description
            newfile.append(record)
        else:
            discarded.append(acc)
    newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
    with open(file_out, 'w') as fout:
        for item in newfile_db:
            fout.write(item)
    numseq = len(list(SeqIO.parse(file_in, 'fasta')))
    print(f'found {numseq} sequences in {file_in}')
    print(f'found {len(newfile)} with correct format')
    print(f'found {len(discarded)} incorrectly formatted accession numbers')

    return discarded
    
def append_primer_seqs(file_in, fwd, rev):
    rev_primer = str(Seq(rev).reverse_complement())
    newfile = []
    for record in SeqIO.parse(file_in, 'fasta'):
        record.seq = fwd + record.seq + rev_primer
        newfile.append(record)
    newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
    with open('mid.fasta', 'w') as fout:
        for item in newfile_db:
            fout.write(item)
    results = sp.run(['mv', 'mid.fasta', file_in])
    
    return len(newfile)
    
def generate_header(file_in, file_out, delimiter):
    newfile = []
    for record in SeqIO.parse(file_in, 'fasta'):
        spec = 'CRABS:' + str(record.description.split(delimiter)[0].replace(' ', '_'))
        record.description = spec
        record.id = record.description
        newfile.append(record)
    newfile_db = [FastaIO.as_fasta_2line(record) for record in newfile]
    with open(file_out, 'w') as fout:
        for item in newfile_db:
            fout.write(item)

    return len(newfile)

def merge_databases(file_in, file_out):
    seqdict = {}
    for file in file_in:
        num_file = len(list(SeqIO.parse(file, 'fasta')))
        print(f'found {num_file} sequences in {file}')
        for record in SeqIO.parse(file, 'fasta'):
            id = '>' + record.id.split('.')[0] + '\n'
            seq = str(record.seq) + '\n'
            if id not in seqdict:
                seqdict[id] = seq
    with open(file_out, 'w') as fout:
        for k, v in seqdict.items():
            fout.write(k)
            fout.write(v)
    num_seq = len(list(SeqIO.parse(file_out, 'fasta')))

    return num_seq