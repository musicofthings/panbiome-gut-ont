# Core image: Python helpers plus minimap2, samtools and chopper.
# Build and push once, then point params.container_core at it:
#   docker build -t ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0 -f docker/Dockerfile docker
#   docker push  ghcr.io/musicofthings/panbiome-gut-ont-core:0.1.0
FROM mambaorg/micromamba:2.10.0-ubuntu24.04
COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml && micromamba clean --all --yes
ENV PATH=/opt/conda/bin:$PATH
