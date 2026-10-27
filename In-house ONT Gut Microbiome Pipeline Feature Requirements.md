# In-house ONT Gut Microbiome Pipeline: Feature Requirements

Oct 27, 2026 · @Shibichakravarthy Kannan

## Purpose and scope

This spec lists the features our in-house ONT gut microbiome pipeline needs, drawn from the BugSeq documentation and adapted to gut samples. BugSeq is built mainly for clinical pathogen detection, isolate AMR and outbreak work, so we keep its strong ONT engineering and quality controls and replace its pathogen-centric parts with gut ecology features: abundance, diversity, strain and function. It is for the Panbiome project, a clinical-grade wellness service rather than a regulated diagnostic, so validation is kept to the bare minimum needed for clinical use (see the platform section).

Priority key: **P0** = needed for a first validated release, **P1** = needed within the first year, **P2** = later or optional. "BugSeq precedent" names the documented behavior we are borrowing or deliberately changing.

Sources read: the BugSeq [quick start](https://docs.bugseq.com/index.html), [data submission](https://docs.bugseq.com/input/data_submission.html), [optimizing results](https://docs.bugseq.com/input/optimizing_results.html), [output overview](https://docs.bugseq.com/output/overview/index.html), [metagenomic classification](https://docs.bugseq.com/output/metagenomic-classification.html), [AMR](https://docs.bugseq.com/output/antimicrobial-resistance.html), [outbreak analysis](https://docs.bugseq.com/output/outbreak-analysis/overview.html), [labs](https://docs.bugseq.com/labs.html), [versioning and validation](https://docs.bugseq.com/change-log/versioning-validation.html), [API](https://docs.bugseq.com/api/summary.html), [Data Explorer](https://docs.bugseq.com/data-explorer/index.html) and the [pipeline change log](https://docs.bugseq.com/change-log/pipeline.html) (versions 3.0 to 8.0.0, as of 27 Oct 2026). The site's results-page sub-pages on report interpretation were not opened.

## Run design: 16 human stool samples per PromethION flow cell

The design is whole-genome shotgun metagenomics on 16 patient stool samples per PromethION flow cell, with no controls in the run and a target of 3 to 4 Gb per sample. The flow cell is on its second use: a human PGx panel runs first, the flow cell is washed, then the gut library is loaded, leaving about 70% of the original pores. The yield figures below are planning arithmetic, not measured results; confirm them in a pilot.

| Design point | Plan | Pipeline consequence |
| --- | --- | --- |
| Multiplexing | 16 patient samples and no in-run controls, using 16 barcodes of a 24-barcode ONT kit. Pick barcodes that the earlier PGx library did not use. | Cross-check barcodes against the PGx run's samplesheet and flag any reads assigned to a barcode that belongs to the earlier library. Control and replicate wells stay supported in the samplesheet for pilots and scheduled control runs. |
| Yield per sample | Target 3 to 4 Gb per sample, so 48 to 64 Gb across 16 samples, or roughly 600,000 to 800,000 reads per sample at a 5 kb mean read length. The rough estimate below puts the expected total at about 35 to 85 Gb, so 3 Gb per sample is likely and 4 Gb is about even odds. | Report per-barcode yield and flag any barcode far below an even share, since stool DNA yield and pooling are uneven. |
| What 4 Gb supports | Species-level profiling, diversity, pathway summaries, AMR gene detection and watchlist flags. Strain-level work needs more: over 5 Gb for near-full reference coverage and over 10 Gb for de novo strain genomes in a published benchmark, so expect genomes only for the most abundant species. Test this in the pilot and, if wanted, run fewer samples per flow cell. | Keep profiling and diversity at P0 and treat MAG recovery as a best-effort P1 output with a depth-based expectation. |
| Depth sufficiency | Decide the minimum read count and the point where detected species stop increasing as reads are added (a rarefaction check on the pilot). | Per-sample depth flag and a saturation plot in every report. |
| Top-up and reruns | Samples that fall short can be pooled again and run on a later library load or flow cell. | Merge reads for the same sample across libraries and runs, and record every run ID that contributed. |
| Stool pre-analytics | Collection kit and stabilization buffer, time to freezing, Bristol stool scale, extraction kit with bead beating, DNA concentration and fragment-size check before library prep. | These are required samplesheet fields and QC gates, and batch effects are tracked by extraction lot and kit. |
| Host content | Human DNA is usually a small fraction of stool, so host depletion is a privacy step more than a performance one, except when bleeding or inflammation raises it. | Keep host removal on by default, store no human reads, and alert when the host fraction is high. |
| Compute | Super-accuracy basecalling of a full PromethION run needs a GPU server. | Plan GPU capacity per run and track basecalling time. |

### Rough yield estimate for a washed flow cell

Bottom line: a second-use flow cell at about 70% of its pores should give roughly 35 to 85 Gb, with a central guess near 60 Gb. That likely covers 3 Gb per sample (48 Gb in total) and gives about even odds for 4 Gb per sample (64 Gb). ONT does not publish yields for washed flow cells, so the second-use figure is my own scaling from the numbers below, not a vendor claim.

| Basis | Figure | Source and caveat |
| --- | --- | --- |
| Fresh PromethION flow cell, best case | Typically 100 to 120 Gb for sheared, size-selected WGS libraries; up to 250 Gb | [University of Minnesota core](https://genomics.umn.edu/service/nanopore-promethion-2-solo-sequencing). A core facility's figure, not ONT's. |
| Fresh flow cell, public runs | Average about 84 Gb per run over 116 public runs; only about 14% exceed 120 Gb | [Community analysis](https://aseqer.com/p/promethion-85gbflowcell). Filtering unknown and library types mixed. |
| Pore guarantee | ONT replaces flow cells with fewer than 5,000 pores | [ONT warranty page](https://nanoporetech.com/support/flow-cells/general-flow-cell-FAQs/what-is-the-warranty-period-on-my-flow-cells). The check covers only the first use; it is not valid after a wash. |
| Wash and reuse | 3 to 6 wash-and-reuse cycles typical; output can at least double over a flow cell's lifetime if washes recover stuck pores | [ONT wash kit know-how](https://nanoporetech.com/document/requirements/flow-cell-wash-kit-exp-wsh004-or-exp-wsh004-xl-know-how) and [ONT news](https://nanoporetech.com/news/news-new-kit-extends-yields-flow-cells). Washing helps only pores in the unavailable state, not saturated ones. |
| Second-run behavior | One experienced user expected a second run to need about 12 hours to match 4 hours of the first; available pores fall with use and storage | [SEA-PHAGES forum](https://seaphages.org/forums/topic/5323/). Anecdotal and about MinION. |
| Buffer life | About 72 hours of run time under optimal conditions | [ONT store page](https://store.nanoporetech.com/promethion-flow-cell-packs-r10-4-1-m-version.html). |
| Scaling to your flow cell | 70% of about 50 to 120 Gb gives 35 to 85 Gb; 70% of the 84 Gb average gives about 59 Gb | My calculation. Yield does not scale exactly with pores, and stool libraries with long fragments can block pores. |
| Need | 16 samples at 3 to 4 Gb gives 48 to 64 Gb | Your target. Uneven pooling means some samples land well below the mean, so aim for 4 Gb as the mean to keep most samples above 3 Gb. |

What 3 to 4 Gb buys, from a short-read benchmark on mock communities ([Nature Microbiology](https://www.nature.com/articles/s41564-026-02334-2)): all strains were detected at about 0.1 Gb, and pathway profiling was reliable at roughly 2 to 5 Gb. Near-full coverage of a reference strain needed over 5 Gb, and de novo strain-level genomes over 10 Gb, so at 3 to 4 Gb expect genomes only for the most abundant species. A stool protocol for long reads recommends at least 6 Gb for assembly ([PMC protocol](https://pmc.ncbi.nlm.nih.gov/articles/PMC8750633/), written for MinION R9.4).

Pilot plan: record available pores at the first pore scan, check per-barcode yield about 24 hours in, and wash and reload if the projected total falls under 48 Gb. ONT also reports barcode carryover under 0.1% after a wash (29 of 30 PromethION runs), which supports using different barcodes for the PGx and gut libraries ([ONT wash kit know-how](https://nanoporetech.com/document/requirements/flow-cell-wash-kit-exp-wsh004-or-exp-wsh004-xl-know-how)).

Running on a washed flow cell adds three pipeline requirements:

- **Pore budget.** Record the pore count at load and the run time in the run metadata. Pool by molarity so each sample gets an even share, and if a barcode finishes short, top it up on a later load or flow cell and merge the reads.
- **Carryover from the PGx library.** Reads from the earlier library can appear in the gut run. Check every run for reads that match the PGx barcodes or target regions, and remove them before analysis.
- **Other people's genetic data.** PGx reads identify other individuals. Keep them out of gut outputs and under the PGx run's access controls.

## Input handling, QC and preprocessing

BugSeq's central lesson for ONT is that data quality is decided before analysis: it warns on fast or hac basecalling, plots adapter prevalence, and parses run metadata from file names and headers. We should enforce the same checks automatically.

| Feature | Requirement | Priority |
| --- | --- | --- |
| Input formats | Accept FASTQ (.fastq/.fq, gzipped or not), unmapped BAM (uBAM) from Dorado, and POD5 as an optional re-basecall entry point. Reject mapped BAM, as BugSeq does. | P0 |
| Samplesheet-driven runs | One samplesheet per run (sample ID, barcode, alias, kit, flow cell, sample type, extraction method, collection date, subject ID, negative or positive control flag). Parse barcode aliases from MinKNOW and Dorado headers. | P0 |
| Basecaller and model audit | Read the model, Dorado version and chemistry from FASTQ or uBAM headers. Flag fast and hac as warnings and sup as the expected setting; block R9.4.1 data from the standard path or route it to a legacy profile. | P0 |
| Demultiplexing and trimming policy | Expect Dorado or MinKNOW demux with barcodes on both ends, and adapters and barcodes already trimmed. Keep a fallback trimmer, but report an adapter and barcode prevalence plot per run. BugSeq removed its own ONT demux in v6.1 because pre-submission demux works better. | P0 |
| Read QC | Per sample: read count, N50, mean and median read length, length histogram, and quality computed correctly (mean Q via error-probability average, not an average of Phred values; BugSeq lists the simple average as a known issue through v8.0.0). Add per-flow-cell and per-channel run QC. | P0 |
| Length and quality filtering | Configurable per assay. Defaults: full-length 16S keep roughly 1,200 to 1,700 bp and Q ≥ 10 to 12; shotgun keep reads ≥ 1 kb and Q ≥ 10. Log how many reads each filter removed. | P0 |
| Low-complexity tail handling | Trim or mask low-complexity read ends (poly-A, poly-T, homopolymer tails), which BugSeq added in v5.6 to improve ONT classification accuracy. | P1 |
| Host depletion | Map to human T2T-CHM13 plus pangenome references with minimap2 and report the percent host. Stool is usually low host, so use a threshold alert when host reads exceed a set percentage (inflammation, bleeding, or contamination). Dynamic alignment-length criteria, as BugSeq uses for nanopore, reduce false removal. | P0 |
| Vector and spike-in screening | Detect and report PhiX, lambda DNA control, and any mock-community or spike-in reads. BugSeq auto-detects T2 phage as an internal control. | P1 |
| Assay auto-detection with override | Detect full-length 16S, 16S+ITS, shotgun, or direct RNA from read content. If the user forces a mode and most reads do not map to that locus, warn (BugSeq v8.0.0). | P1 |
| Read-depth sufficiency flag | Flag samples below a minimum read count for the chosen assay (to be set in validation) so low-depth profiles are not silently over-interpreted. BugSeq recommends 40X median depth for isolates; gut metagenomes need a count-based rule instead. | P0 |
| Upload and file hygiene | Prefer fewer, larger per-barcode FASTQs (BugSeq advises 100,000 to 500,000 reads per file) and gzip. Provide a local pre-submission validator. | P2 |

## Taxonomic profiling

BugSeq combines several classifiers into one ensemble (BugSplit, its original Bayesian read-alignment method, plus others) on a curated reference called BugRef, and runs a separate 16S track on a curated 16S database. For the gut we need the same two ideas, a curated reference and more than one method, tuned for community profiling rather than pathogen calls.

| Feature | Requirement | Priority |
| --- | --- | --- |
| Full-length 16S track | Species-level profiling of \~1.5 kb reads against a curated database (species-level curation, NCBI/GTDB-consistent taxonomy, removal of contaminated entries, intra-species variation). BugSeq built its own 16S database for this reason, and reports unclassified read counts and suggested taxa from consensus identity. | P0 |
| Shotgun metagenomic track | Read-based classification of long reads against a genome database, with species-level abundance estimates and a min-identity and min-alignment-fraction filter. | P0 |
| Ensemble or dual-method classification | Run at least two independent methods (for example alignment-based and k-mer or marker-based) and reconcile them. BugSeq's v5.3 ensemble improved low-abundance detection while holding precision. | P1 |
| Curated gut reference database | Versioned, GTDB-aligned reference including a gut genome collection (UHGG, plus our own cohort MAGs), with archaea, fungi, phage and plasmids represented. Track database version in every output. | P0 |
| Taxonomy policy | One taxonomy (GTDB or NCBI) chosen per release, with a crosswalk table to the other, since gut names differ (for example Faecalibacterium and Lachnospiraceae splits). Record the taxonomy version used. | P0 |
| Abundance estimation | Report relative abundance with a clearly stated denominator, plus reads per million. BugSeq changed its denominator to include host reads in v5.4, which shows how much this choice shifts values, so make it explicit and configurable. | P0 |
| Correction for 16S copy number and read length | Apply gene-copy-number correction as an option for 16S profiles, and normalize shotgun counts by genome length. | P1 |
| Detection thresholds | Per-assay minimum reads and minimum genome breadth or unique-read support before a taxon is called, to cut false positives from database near-neighbors. BugSeq reports reads, unique alignments and genome coverage for each taxon. | P0 |
| Strain and subspecies resolution | Strain-level calls where coverage allows: SNV profiles, MLST for key gut taxa (for example E. coli, Klebsiella, C. difficile), and strain sharing across timepoints or donors. | P1 |
| Viral and phage profiling | Report gut virome (crAssphage, other phages) from shotgun data. Direct RNA is optional and BugSeq has since added better ONT direct-RNA support. | P2 |
| Fungal profiling | Long-read ITS (or ITS from shotgun) with percent identity and percent reference covered, as BugSeq added in v8.0.0, using a curated fungal database. | P1 |
| Pathobiont and clinically relevant flags | Replace BugSeq's body-site pathogenicity model with a configurable gut watchlist (C. difficile, enteropathogenic E. coli, Salmonella, Shigella, Campylobacter, Vibrio, Klebsiella pneumoniae, toxigenic markers) with lab-set thresholds. BugSeq's default is 1% abundance outside CSF and respiratory samples; ours should be set during validation. | P1 |
| Per-read outputs | Per-read classification table and a Kraken-style report so downstream tools can reuse results; Krona-style interactive view. | P1 |

## Assembly, MAGs, resistance and function

Long reads let a gut pipeline recover near-complete genomes, link AMR genes to plasmids and hosts, and find insertion-sequence context. BugSeq's ONT assembly work (ensemble assembly, polishing, frameshift correction, circularization) is the main precedent to copy.

| Feature | Requirement | Priority |
| --- | --- | --- |
| Metagenome assembly | Long-read metagenome assembler run per sample, with optional co-assembly across timepoints of one subject. BugSeq moved to an ensemble approach in v8.0.0 to recover AMR genes and insertion-sequence flanks. | P0 |
| Assembly polishing | Polish with ONT-native tools to cut methylation-driven errors; BugSeq reports about 50% fewer assembly errors from this in internal benchmarks. Apply frameshift correction selectively, for example when fragmented BUSCOs outnumber complete ones (BugSeq v7.0.0). | P0 |
| Binning and MAG quality | Bin contigs into MAGs, assign GTDB taxonomy, and score completeness and contamination (MIMAG/MISAG tiers). Keep contigs of at least 1 kb for DNA, as BugSeq does, and allow contigs to belong to more than one bin where genomes are near-identical. | P1 |
| Circular contig and plasmid detection | Identify circular contigs, classify plasmids with replicon and relaxase typing, report predicted mobility (conjugative, mobilizable, non-mobilizable) as BugSeq does since v5.3, and name plasmids with stable cluster IDs (MOB-Cluster style). | P1 |
| AMR gene detection | Detect acquired resistance genes with a curated database; report only complete genes, suppress intrinsic genes per taxon, and show identity and coverage with a confidence tier (BugSeq: very high at 100% identity and coverage, high at 100% identity with partial coverage, moderate below). | P0 |
| AMR host and context linkage | For each resistance gene report the contig, the assigned taxon or MAG, and whether it sits on a plasmid or next to an insertion sequence. This is the main long-read advantage. | P1 |
| Phenotype prediction | Out of scope for a community profile: gut metagenomes cannot give reliable per-organism MIC phenotypes. Report genotype only, and reserve phenotype logic for cultured isolates (see out-of-scope section). | P0 |
| Virulence and toxin genes | Gene panel for gut pathogens: C. difficile toxins A and B, E. coli pathotypes and Shiga toxin, Salmonella, Vibrio cholerae toxin, B. fragilis toxin. BugSeq reports many of these for isolates. | P1 |
| Functional profiling | Predict genes on contigs and reads, then summarize pathways and modules: butyrate and other SCFA synthesis, bile acid metabolism, mucin degradation, CAZymes, vitamin synthesis. | P1 |
| Mobile elements | Report insertion sequences, integrons, prophage and CRISPR where assembly allows. | P2 |
| Methylation signals | Keep modified-base calls (5mC, 6mA) from Dorado for optional motif discovery and binning support; do not discard them at basecalling. | P2 |

## Quantification, controls and diversity

BugSeq has no ecology layer, since its focus is detection, so this section is mostly new. It does give us a template for control handling: normalization against negative and internal controls, with the denominator changed in v6.0 to total reads minus host reads so human read fraction does not skew the comparison.

| Feature | Requirement | Priority |
| --- | --- | --- |
| Negative and positive controls | Patient runs carry no in-run controls, so run an extraction blank and a mock community (for example ZymoBIOMICS) on a fixed schedule: each new reagent or kit lot, each instrument or operator change, and at least monthly. Flag taxa in patient samples that match the latest blank's contaminant list. | P0 |
| Mock community accuracy check | On each scheduled control run, compare observed to expected composition and report bias and false-positive taxa. Patient runs are released only while the latest control run is within limits set in validation. | P0 |
| Absolute abundance (optional) | Support a spike-in (for example a known-copy synthetic or foreign-genome spike) to convert relative to absolute counts. Relative data alone can mislead when total bacterial load differs between samples. | P1 |
| Sample tracking and swap checks | Detect index hopping or barcode crosstalk with strict dual-barcode demux, and fingerprint samples (SNV or species signature) to catch swaps across timepoints of one subject. | P1 |
| Alpha diversity | Observed richness, Shannon, Simpson, Faith's PD (needs a tree). Report with rarefaction or coverage-based curves so depth differences are visible. | P0 |
| Beta diversity | Bray-Curtis, Jaccard, Aitchison (CLR) and weighted UniFrac, with PCoA and PERMANOVA across metadata groups. | P0 |
| Compositional methods | Treat counts as compositional: CLR transform, plus differential abundance using compositionally aware tools, with multiple-testing correction and effect sizes. | P1 |
| Cohort and longitudinal views | Compare a sample to a reference healthy cohort, to the same subject's earlier samples, and to treatment events. BugSeq's "cluster address" alerting (alert when a new sample falls within a set distance of an existing one) is a useful model for flagging strain persistence or transmission in FMT and antibiotic studies. | P1 |
| Dysbiosis and health indices | Optional score such as a dysbiosis index, with the reference cohort and method documented, and not shown as a diagnosis. | P2 |
| Metadata-aware analysis | Covariates (age, diet, medication, antibiotic exposure, collection and storage method) carried through every statistic, and batch (extraction, run, flow cell) tracked as a variable. | P1 |

## Reports, visualization and interpretation

BugSeq produces an interactive run-level summary and a per-sample report, both built on MultiQC, with PDF export, a zip of all outputs, Excel sheets and Kraken-format files. The structure fits our needs; the content changes.

| Feature | Requirement | Priority |
| --- | --- | --- |
| Run summary report | Interactive HTML plus PDF: run QC, basecaller audit, adapter prevalence, control results, per-sample QC table with pass, warn and fail flags, and an executive summary of warnings at the top (BugSeq's pattern). | P0 |
| Per-sample report | Composition bar and Krona views, top taxa table with reads, unique alignments and coverage, diversity metrics, AMR and virulence tables, plasmids, MAG table, functional pathway summary. | P0 |
| Cohort report | Across samples: ordination plot, heatmap, group comparisons, longitudinal trajectories, and a downloadable feature table (BIOM and TSV) for R and Python. | P1 |
| Table filtering and pinned columns | Filter report tables by value or number and pin the first column, both added by BugSeq in v8.0.0 and v5.5. Hide advanced columns by default. | P1 |
| Genome coverage view | Per-taxon coverage plots for metagenomic samples, rendered on demand so a report with thousands of plots stays usable (BugSeq v5.6 and v6.0 lesson). | P2 |
| Clear warnings | Text warnings for anomalous data: wrong sample type, low depth, high host fraction, old basecaller, control failure, contamination signal. | P0 |
| Plain-language summary (optional) | An LLM summary of results, off by default, shown separately from the data and always labeled as needing review; BugSeq offers this with a lab-level off switch. | P2 |
| Export formats | BIOM, TSV, JSON, Excel, Newick for trees, and standard sequence files (FASTA of MAGs, GFF of annotations). | P0 |
| Dark mode and accessibility | Light and dark themes (BugSeq v6.1) and colorblind-safe palettes. | P2 |

## Platform: integration, versioning, validation and security

BugSeq's platform design is where its clinical maturity shows: pinned versions, a re-run validation tool, lab-level configuration and an open API. For Panbiome they matter because reports will inform clinical-grade wellness advice, so runs must be reproducible and traceable even without a full regulatory validation.

| Feature | Requirement | Priority |
| --- | --- | --- |
| Workflow engine | A containerized, portable workflow (Nextflow with per-tool containers) so runs are identical on the local GPU workstation, cluster or cloud. | P0 |
| Versioned releases | Tagged versions (v1.2.3) pinned per lab or project, a Latest channel for development, and a quarterly release cadence with a defined support window. BugSeq supports tagged versions for 1 year with a 3-month end-of-life warning. | P0 |
| Version stamping | Every report and output file records pipeline version, tool versions, database versions, taxonomy version and all parameters. | P0 |
| Validation tooling | Re-run a set of earlier samples on a candidate version and show side-by-side differences (BugSeq's Validations tab). Keep a locked reference set: mock communities and truth-known samples with expected outputs. | P0 |
| Minimum validation package | Keep it small and documented: (1) accuracy on a gut mock community with known composition; (2) repeatability on replicate stool samples across at least two runs, flow cells and operators; (3) a limit-of-detection check for the key watchlist taxa by dilution or spike-in; (4) blank runs for contamination; (5) a locked pipeline and database version with a written SOP; (6) wellness-only report wording with no disease-diagnosis claims. Confirm with regulatory counsel that this positioning holds under Indian rules before launch. | P0 |
| Automated change log | Added, fixed, changed and known-issues sections for every release, as BugSeq maintains. | P1 |
| Lab and project model | Projects or labs with roles (submitter, reviewer), default submission options that can be enforced, shared analyses, and per-lab thresholds for QC, detection and alerts. | P1 |
| API | REST API with an OpenAPI spec: upload data, start a run, and fetch results, plus a Python client. | P1 |
| LIMS and ELN integration | Samplesheet import from the LIMS, report push back, and sequencer integration (watch an output folder or a MinKNOW run). BugSeq integrates with BaseSpace for Illumina; our equivalent is the ONT run folder and the LIMS. | P1 |
| Data Explorer and custom queries | Cross-run query over stored results (choose tables and fields, export to CSV), backed by a database of per-sample results rather than flat files. | P1 |
| Notifications | Email or chat notice when a run finishes or fails QC, with configurable alerts such as a pathogen watchlist hit or control failure. | P1 |
| Security and privacy | Encryption at rest and in transit, role-based access, audit trail, de-identified subject IDs, and data retention rules. Human reads must be removed or access-controlled to protect donor privacy and meet Indian DPDP Act obligations. | P0 |
| Compute and cost tracking | Per-run cost, runtime, and resource use so we can plan GPU basecalling and assembly capacity. | P2 |

## Suggested tools and phased roadmap

These are candidate open-source tools for each stage, to benchmark on a mock community and a few in-house stool samples before we commit. They are suggestions from general knowledge, not taken from BugSeq's docs, which do not name most of its internal tools.

| Stage | Candidate tools | Notes |
| --- | --- | --- |
| Basecalling, demux, trimming | Dorado (sup model, dual-barcode demux, trimming) | Run on GPU; keep uBAM with modified-base tags |
| Run and read QC | NanoPlot, chopper or NanoFilt, MultiQC, pycoQC | MultiQC also matches BugSeq's report engine |
| Host depletion | minimap2 against T2T-CHM13 | Check human pangenome as a second reference |
| 16S full-length profiling | Emu, plus EPI2ME wf-16s as a cross-check | Compare against a curated 16S database |
| Shotgun profiling | Kraken2 with Bracken, Sylph, minimap2 read mapping to a gut genome set | Run two methods and reconcile |
| Assembly and polishing | metaFlye or myloasm, Dorado polish or Medaka | Test on R10.4.1 sup data |
| Binning and MAG QC | SemiBin2 or MetaBAT2, CheckM2, GTDB-Tk | Long-read binning may need coverage across timepoints |
| AMR, plasmids, virulence | AMRFinderPlus, CARD RGI, geNomad, MOB-suite, VFDB | Report genotype only |
| Function | Bakta or Prodigal, KEGG or eggNOG-mapper, dbCAN, gutSMASH | Short-read tools such as HUMAnN may need adaptation for long reads |
| Statistics | scikit-bio, phyloseq or microbiome R packages, ANCOM-BC2, MaAsLin3 | Compositionally aware methods |
| Workflow base | Nextflow with nf-core/taxprofiler and nf-core/mag as starting points | Add our QC, control and reporting layers |

A suggested build order follows. Each phase ends with a validation gate before the next starts.

1. **Phase 1, core profiling (months 0 to 3):** samplesheet and QC, basecaller audit, host depletion, full-length 16S and shotgun profiling, control handling, run and sample reports, version stamping. Gate: mock community accuracy and run-to-run reproducibility meet targets.
2. **Phase 2, depth (months 3 to 6):** diversity and cohort statistics, assembly, MAGs, AMR with plasmid and host linkage, gut watchlist flags. Gate: AMR and MAG results agree with isolate sequencing or short-read data on a reference panel.
3. **Phase 3, function and strain (months 6 to 9):** pathway profiling, strain tracking across timepoints, longitudinal views, optional absolute quantification.
4. **Phase 4, platform (months 9 to 12):** API, LIMS integration, Data Explorer style queries, validation tooling, roles and alerting, and a documented minimum validation dossier.

The month ranges are rough planning guesses and depend on team size.

## BugSeq features we deliberately leave out

Much of BugSeq's changelog serves clinical pathogen and public-health work, not gut ecology. Leaving these out keeps the first release focused.

- **Body-site pathogenicity prediction** (CSF, respiratory machine-learning thresholds): replace with the gut watchlist above.
- **Isolate-only analyses**: refMLST outbreak clustering and cluster addresses, isolate summary Excel, MycoSNP, serotyping for single isolates. Outbreak tooling is also not offered by BugSeq for older ONT chemistries (R9.4.1, R10.3). Revisit only if we add a cultured-isolate workflow.
- **Phenotypic AMR prediction** with CLSI or EUCAST breakpoints, M. tuberculosis, HIV and influenza resistance, and organism-specific rules: these need cultured, single-organism input and are not valid for a mixed gut community.
- **Virus-specific typing** (SARS-CoV-2 lineages, Nextclade, Influenza genotyping, wastewater lineage abundance): not relevant to stool.
- **Illumina, PacBio and Ion Torrent paths**: out of scope for an ONT-only pipeline, though a short-read validation arm is useful for benchmarking.
- **Hosted multi-tenant billing and BaseSpace integration**: an in-house deployment needs neither.

Open questions: the total yield of a washed, second-use flow cell at about 70% of its pores (answered by the pilot), and the weekly sample volume, which sets flow cell and GPU planning.
