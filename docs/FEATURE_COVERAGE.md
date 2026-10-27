# Coverage of the requirements spec

Compared against the feature requirements document ("In-house ONT Gut Microbiome Pipeline: Feature Requirements"). **Built** means code exists and, for Python helpers, is unit-tested. It does not mean the whole workflow has been validated on real data.

## Input, QC, preprocessing

| Feature | Priority | Status |
| --- | --- | --- |
| FASTQ and unmapped BAM input | P0 | Built. POD5 re-basecall entry not built. |
| Samplesheet-driven runs, control flags | P0 | Built (EPI2ME columns plus metadata). Barcode aliases come from the sheet; MinKNOW alias parsing is not built. |
| Basecaller and model audit | P0 | Built (reads `basecall_model_version_id`; warns on fast/hac/unknown). R9.4.1 is not blocked. |
| Demultiplexing and trimming policy | P0 | Policy only: expects pre-demultiplexed, trimmed reads and reports adapter prevalence (one adapter motif plus an optional FASTA). No fallback trimmer. |
| Read QC with correct mean Q | P0 | Built. Per-flow-cell and per-channel QC not built. |
| Length and quality filtering | P0 | Built (chopper). Per-filter removal counts not logged. |
| Low-complexity tail handling | P1 | Not built. |
| Host depletion with privacy handling | P0 | Built (minimap2, partial alignments kept, human reads never stored). |
| Vector and spike-in screening | P1 | Not built. |
| Assay auto-detection with override | P1 | Not built; `--assay` is explicit. |
| Read-depth sufficiency flag | P0 | Built (Gb and read-count rules, run-median balance). |

## Taxonomic profiling

| Feature | Priority | Status |
| --- | --- | --- |
| Full-length 16S track | P0 | Built (Emu); database supplied by you. |
| Shotgun track | P0 | Built (Kraken2/Bracken, sylph). |
| Ensemble classification | P1 | Built (two-method agreement rule). |
| Curated gut reference database | P0 | Not included; you supply GTDB-based databases. |
| Taxonomy policy and crosswalk | P0 | Requires one taxonomy; optional synonyms file. No NCBI/GTDB crosswalk. |
| Abundance estimation, explicit denominator | P0 | Built: relative abundance among kept species from the primary method. Reads-per-million not built. |
| 16S copy-number correction | P1 | Not built. |
| Detection thresholds | P0 | Built (min reads, min ANI, min coverage); unique-read support not built. |
| Strain and subspecies resolution | P1 | Not built. |
| Viral/phage and fungal profiling | P2/P1 | Not built (depends on database content). |
| Gut watchlist | P1 | Built (starter list, placeholder thresholds). |
| Per-read outputs, Krona | P1 | Kraken2 per-read output optional; Krona built for Kraken2 results. |

## Assembly, resistance, function

| Feature | Priority | Status |
| --- | --- | --- |
| Long-read metagenome assembly | P0 | Built (metaFlye). Co-assembly across timepoints not built. |
| Polishing | P0 | Medaka built. Selective frameshift correction not built. |
| Binning and MAG quality | P1 | Built (SemiBin2, CheckM2, optional GTDB-Tk, MIMAG tier). |
| Circular contigs and plasmids | P1 | Circularity (Flye) and plasmid score (geNomad) built. Replicon/relaxase typing and mobility not built. |
| AMR gene detection with confidence tier | P0 | Built (AMRFinderPlus, complete genes only, BugSeq-style tiers). Intrinsic-gene suppression per taxon not built. |
| AMR host and context linkage | P1 | Contig, circularity, plasmid, MAG and taxon built. Insertion-sequence context not built. |
| Virulence genes | P1 | Partial: AMRFinderPlus `--plus` output only. |
| Functional profiling | P1 | Built (eggNOG-mapper; depth-weighted KO, module, CAZy; five-KO starter set that needs curation). |
| Mobile elements, methylation | P2 | Not built. |

## Quantification, controls, diversity

| Feature | Priority | Status |
| --- | --- | --- |
| Controls: scheduled control runs and status | P0 | Built (PASS/FAIL/EXPIRED/MISSING, contaminant flags). |
| Mock community accuracy check | P0 | Built (Bray-Curtis, unexpected abundance, missing taxa). |
| Absolute abundance by spike-in | P1 | Not built. |
| Sample swap and crosstalk checks | P1 | Not built. |
| Alpha and beta diversity | P0 | Built (Shannon, Simpson, richness, evenness; Bray-Curtis, Jaccard, Aitchison; PCoA; rarefaction). Faith's PD and weighted UniFrac not built. |
| Differential abundance | P1 | Not built (CLR distance and PERMANOVA only). |
| Cohort and longitudinal views | P1 | Not built. |
| Dysbiosis index | P2 | Not built. |
| Metadata-aware statistics | P1 | Partial (group column for color and PERMANOVA). |

## Reports and platform

| Feature | Priority | Status |
| --- | --- | --- |
| Run summary and per-sample reports (HTML) | P0 | Built, self-contained, light/dark. PDF export not built. |
| Warnings block | P0 | Built. |
| Export formats | P0 | TSV, JSON, BIOM 1.0 JSON built. FASTA of MAGs published. Excel not built. |
| Table filtering, coverage view, LLM summary | P1/P2 | Not built. |
| Workflow engine, containers | P0 | Built (Nextflow, one container per tool). |
| Version stamping | P0 | Partial: pipeline version, tool versions, parameters recorded. Database versions are not recorded automatically. |
| Re-run validation tooling, locked reference set | P0 | Not built. |
| Minimum validation package | P0 | Not built (it is laboratory work); thresholds are placeholders. |
| Lab/project roles, API, LIMS, Data Explorer | P1 | Not built (deployment layer). |
| Security and privacy | P0 | Human reads are not stored. Access control, encryption and audit trail are deployment concerns. |
