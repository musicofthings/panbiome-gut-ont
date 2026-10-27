# Databases

All databases are supplied by you and passed as parameters. Nothing in this file is downloaded by the workflow. Sizes and commands below were checked on 2026-10-28 against the pinned images and the publisher pages named in `docs/VALIDATION_LOG.md`. They were not downloaded in that check.

Shotgun species names are reconciled across Kraken2/Bracken and sylph, so those two databases have to be the same GTDB release. The prebuilt Kraken2 GTDB archive on the Langmead index page is **GTDB v226**. Use the sylph GTDB r226 database and the r226 taxonomy files with it. Do not pair that Kraken archive with a sylph r232 or r220 database.

The pinned GTDB-Tk image is 2.8.0. Its install table accepts reference package **R232** (tool versions 2.7.0 through current). R226 stops at GTDB-Tk 2.6.1, and R220 stops at 2.6.1. A GTDB-Tk database for this image is a different release from the shotgun pair above. GTDB-Tk is optional.

| Parameter | What | Command and size |
| --- | --- | --- |
| `host_ref` | T2T-CHM13v2.0 minimap2 index. Keep it outside the repo. | `GCA_009914755.4_T2T-CHM13v2.0_genomic.fna.gz` from `https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/009/914/755/GCA_009914755.4_T2T-CHM13v2.0/`. A one-byte range request reported 932696125 bytes. NCBI lists the assembly as 3.1 Gb. Then `minimap2 -x map-ont -d chm13v2.0.map-ont.mmi chm13v2.0.fa`. The index size was not measured. |
| `kraken2_db` | Kraken2 + Bracken, GTDB v226 representative genomes. Bacteria and archaea. This archive does not include a human library. | `https://genome-idx.s3.amazonaws.com/kraken/k2_gtdb_genome_reps_20250609.tar.gz`. Range request: 537801719465 bytes. The index page lists the extracted index as 644.0 GB and says its Bracken databases are 50, 75, 100, 150, 200, 250 and 300-mers. After extracting, run `bracken-build -d DB -t THREADS -k 35 -l 1000` so `database1000mers.kmer_distrib` exists. Struo2 was not confirmed. |
| `sylph_db` | sylph GTDB r226 database. The pinned sylph 1.0.0 accepts `.syldb` and `.syl2db`. | `http://faust.compbio.cs.cmu.edu/sylph-stuff/gtdb-r226-c200-dbv2.syl2db`. Range request: 14272284891 bytes. The sylph docs list this file as the r226 `-c 200` two-stage database. Pass that file to `--sylph_db`. |
| `sylph_lineage_map` | Accession to GTDB lineage, same release as `sylph_db`. | `bac120_taxonomy_r226.tsv.gz` (7607942 bytes) and `ar53_taxonomy_r226.tsv.gz` (227138 bytes) from `https://data.gtdb.ecogenomic.org/releases/release226/226.0/`. Decompress, then `python3 bin/make_sylph_lineage_map.py bac120_taxonomy_r226.tsv ar53_taxonomy_r226.tsv > gtdb_r226_map.tsv`. |
| `emu_db` | Emu database (16S) | The pinned image has `emu build-database`. A current prebuilt database URL was not confirmed. |
| `checkm2_db` | CheckM2 DIAMOND database. The workflow passes it to `--database_path`. | `checkm2 database --download --path DIR` in the pinned CheckM2 1.1.0 image. The CheckM2 README names the file `uniref100.KO.1.dmnd` inside `CheckM2_database/`. Zenodo record 14897628 file `checkm2_database.tar.gz` is 1735095710 bytes. |
| `gtdbtk_db` | GTDB-Tk R232 reference directory. The workflow sets `GTDBTK_DATA_PATH` to this path. Optional. | `wget https://data.gtdb.ecogenomic.org/releases/release232/232.0/auxillary_files/gtdbtk_package/full_package/gtdbtk_r232_data.tar.gz` then `tar xvzf gtdbtk_r232_data.tar.gz`. Range request: 60806405195 bytes. The GTDB-Tk 2.8.0 install page says the R232 external data is about 100 GB, and bacterial classification needs about 140 GB of memory. |
| `amrfinder_db` | AMRFinderPlus database directory, the same directory passed to the updater. | `amrfinder_update --database DIR` in the pinned 4.2.7 image. `amrfinder -u` is the same update. A HEAD of `https://ftp.ncbi.nlm.nih.gov/pathogen/Antimicrobial_resistance/AMRFinderPlus/database/latest/` summed to 129839548 bytes. Pass `DIR` to `--amrfinder_db`. |
| `genomad_db` | geNomad database directory. | `genomad download-database DIR` in the pinned 1.13.0 image. That image's `releases.txt` selects database 1.9: `https://portal.nersc.gov/genomad/__data__/genomad_db_v1.9.tar.gz` (842023773 bytes). The geNomad README says the unpacked directory is `genomad_db`. Pass `DIR/genomad_db`. |
| `eggnog_db` | eggNOG 5.0.2 data directory for the pinned mapper 2.1.15. The workflow passes only `--data_dir`. | `download_eggnog_data.py --data_dir DIR` is the image command, and `-D` is what skips the DIAMOND file. Its `BASE_URL` host `eggnogdb.embl.de` did not resolve. The same three paths on `https://eggnog5.embl.de/download/emapperdb-5.0.2/` did: `eggnog.db.gz` 6776977123 bytes, `eggnog.taxa.tar.gz` 72797584 bytes, `eggnog_proteins.dmnd.gz` 5208806170 bytes. eggNOG-mapper v3's eggNOG 7 download is a different database and does not apply to this image. |

## Mock community expected composition

`mock_expected` is a TSV with columns `taxon` and `expected_rel_abundance`. Use the **species names exactly as your GTDB-based database reports them**, and the abundance the mock vendor certifies for your sequencing method (DNA, not cells, if you start from DNA).

```
taxon	expected_rel_abundance
Escherichia coli	0.10
Bacillus subtilis	0.10
```

(The values above are an example of the format only.)

## Name synonyms

If the two classifiers still disagree on a few names, list them in `taxa_synonyms` (TSV, alias then canonical name, no header).
