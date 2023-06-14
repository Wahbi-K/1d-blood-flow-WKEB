Evaluating *in silico* trials
=============================

The following code block illustrates how to create, run, and analyse trials
using ``desist``. To run trials in parallel you can either use the ``parallel``
executable or use parallelisation functionality through the ``QCG-PilotJob``
runner. Both provide the ability to run trials in a massively parallel fashion.
Note: when running on large ``SLURM``-based allocations using ``parallel`` it
might be required to forward the current environment to all parts of the
allocation. Depending on the cluster configuration, this process might be
opaque and error-prone. A way to avoid these errors is to opt for the
``QCG-PilotJob`` based runner through the ``--qcg`` flag, which automatically
take over the resource management within the allocation.

.. code-block:: bash

    # the name of the trial directory
    trial=demo-trial

    # creating a trial with `num` patients
    desist trial create $trial -n $num

    # creating a trial from a in/exclusion file
    desist trial create $trial -c criteria.yml

    # creating a trial using Singularity containers
    desist trial create $trial -c criteria.yml -s $HOME/containers

    # printing the commands to run the trial without evaluating
    desist trial run $trial -x

    # running the trial sequentially
    desist trial run $trial

    # running the trial in parallel
    desist trial run $trial --parallel | parallel

    # running the trial in parallel using the QCG-PilotJob runner
    desist trial run $trial --qcg

    # generating trial outcome
    desist trial outcome $trial


Running trials on HPC environments
----------------------------------

The trials can be evaluated in parallel using either ``--parallel`` or ``--qcg``
flags. Both flags dispatch the evaluation of the individual trials to an
external runner, ``GNU Parallel`` and ``QCG-PilotJob`` respectively. These take
control over the required jobs that need to be evaluated---consisting of the
required ``desist patient run`` commands with the corresponding flags---and
their scheduling on the available hardware.

Typically jobs are scheduled on HPC systems through job schedulers, such as
``SLURM``, and require an input file. The following snippet shows an
illustrative job description for running trials using ``desist``. This example
considers 8 nodes with 16 tasks each.


.. code-block:: bash

   #!/bin/bash
   #SBATCH --job-name=trial-name
   #SBATCH --nodes=8
   #SBATCH --ntask-per-node=16
   #SBATCH --partition=normal
   #SBATCH --exclusive
   #SBATCH --time=02:00:00

   # The location and name of the trial.
   trialpath="$HOME/trials"
   trialname="${SLURM_JOB_NAME}"
   trial="$trialpath/$trialname"

   # The directory containing the Singularity *.sif containers.
   containerdir="$HOME/containers"

   # The output directory used for storing all generated output.
   storagedir="$HOME/desist-output"
   outdir="$storagedir/trial-${SLURM_JOB_NAME}-${SLURM_JOB_ID}"
   mkdir -p "$outdir"

   # The output directory where the compressed trial archives are placed.
   archive_dir="$outdir-archive"

   # A local working directory, ideally located on local scratch space.
   workdir="$TMPDIR/scratch-${SLURM_JOB_ID}"
   mkdir -p "$workdir"

   # Report back general job information.
   echo "$(date)": init
   echo "user: ${USER}"
   echo "hostname: ${HOSTNAME}"
   echo "nodelist: ${SLURM_JOB_NODELIST}"
   echo "tasks for job: ${SLURM_NTASKS}"
   echo "tasks per node: ${SLURM_NTASKS_PER_NODE}"

   # Load required dependencies through the module system (or other).
   module load 2020
   module load mpicopy/4.2-gompi-2020a
   module load Python/3.8.2-GCCcore-9.3.0
   module list

   # Assert the trial directory is present on the filesystem.
   if [ ! -d "$trial" ]; then
   	echo "Provided trial directory ${trial} does not exist."
   	exit 1
   fi

   # Scatter containers and trial to all nodes (not required when nodes use a
   # shared scratch space. If ``mpicopy`` is not present, consider ``sbcast``.
   mpicopy -o "$workdir/" "$containerdir"
   mpicopy -o "$workdir/" "$trial"

   # Move into the scratch disk and run the trials.
   cd "$workdir" || {
   	echo "The workdir $workdir does not exist"
   	exit 1
   }

   echo "$(date)": simulations start

   time desist trial run "$trialname" \
   	--container-path "$workdir/containers" \
   	--clean-files 1mb \
   	--qcg

   echo "$(date)": all simulations complete
   echo "$(date)": transferring data...

   # Gather outcome in the output directory and merge together
   sgather -v --recursive --compress --preserve "$workdir/$trialname" "$outdir"
   wait

   cp -rp "$outdir".*/* "$outdir"
   wait

   echo "$(date)": data transfer complete...
   echo "$(date)": generating trial outcome and trial archival...

   # Evaluate trial outcome model once all data is retrieved and merged.
   desist trial outcome "$outdir"

   # Generate trial archive by extracting files of interest.
   desist trial archive "$outdir" "$archive_dir" \
           -a isct.log

   # Generate a compressed version of the archived trial. This is evaluated from
   # the base directory to prevent possible empty patient directories.
   tar -C "$(dirname "$archive_dir")" -Jcf "$archive_dir.tar.xz" "$(basename "$archive_dir")"

   # Remove any intermediate files created during the file retrieval with
   # ``sgather``, which are typically appended with ``.hostname``.
   rm -r "${outdir:?}".*

   echo "$(date)": completed
