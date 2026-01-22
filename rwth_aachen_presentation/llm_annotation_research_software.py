"""
llm_annotation_research_software.py

Annotate DeLFI journal articles for research software existence using OpenAI's API.
Classifies each PDF file, whether it contains research software (1) or not (0).
The following research software definition is used:

”Research software includes source code files, algorithms, scripts, computational workflows and executables that
were created during the research process or for a research purpose.”
- Source: (Gruenpeter et al., Defining Research Software: a controversial discussion, 2021, https://doi.org/10.5281/zenodo.5504016)

Usage:
    # Test mode (50 random samples)
    python llm_annotation_research_software.py --test
    
    # Full run
    python llm_annotation_research_software.py
    
    # Resume from checkpoint
    python llm_annotation_research_software.py --resume results/checkpoint_gpt-4o-mini_2026-01-21.csv
"""


import json
import os
import base64
import random
import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm
import time


# Load environment variables
load_dotenv()


# =============================================================================
# 1) CONFIGURATION
# =============================================================================

# OpenAI settings (will be overridden by command-line args)
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0 # For reproducability

# Processing settings
CHECKPOINT_FREQUENCY = 50  # Save progress every N PDFs
MAX_RETRIES = 3  # Retry failed API calls
RETRY_DELAY_SECONDS = 5  # Wait between retries
MAX_CONSECUTIVE_ERRORS = 10  # Stop if this many errors in a row (circuit breaker)
RANDOM_SEED = 42

# Paths
DATA_DIR = Path("../data")
RESULTS_DIR = Path("results")

# LNI to year mapping
LNI_MAPPING = {
    "lni37": 2003,
    "lni52": 2004,
    "lni66": 2005,
    "lni87": 2006,
    "lni111": 2007,
    "lni132": 2008,
    "lni153": 2009,
    "lni169": 2010,
    "lni188": 2011,
    "lni207": 2012,
    "lni218": 2013,
    "lni233": 2014,
    "lni247": 2015,
    "lni262": 2016,
    "lni273": 2017,
    "lni284": 2018,
    "lni297": 2019,
    "lni308": 2020,
    "lni316": 2021,
    "lni322": 2022,
    "lni338": 2023,
    "lni356": 2024,
    "lni369": 2025,
}

# JSON schema for structured output
JSON_SCHEMA_CONFIG = {
    "name": "research_software_classification",
    "schema": {
        "type": "object",
        "properties": {
            "label_research_software": {
                "type": "integer",
                "enum": [0, 1],
                "description": "Whether the DeLFI article contains research software"
            },
            "label_research_software_justification": {
                "type": "string"
            },
            "label_software_evaluation": {
                "type": "integer",
                "enum": [0,1],
                "description": "Whether the DeLFI article evaluates the research software"
            },
            "label_software_evaluation_justification": {
                "type": "string"
            },
            "label_empirical_study": {
                "type": "integer",
                "enum": [0,1],
                "description": "Whether the DeLFI article is an empirical study"
            },
            "label_empirical_study_justification": {
                "type": "string"
            }
        },
        "required": ["label_research_software", 
                     "label_research_software_justification",
                     "label_software_evaluation",
                     "label_software_evaluation_justification",
                     "label_empirical_study",
                     "label_empirical_study_justification"],
        "additionalProperties": False
    },
    "strict": True
}


# =============================================================================
# 2) PDF EXCLUSION 
# =============================================================================

# Full proceedings PDFs to exclude (manually identified)
FULL_PROCEEDINGS_SET = {
    DATA_DIR / "lni153/lni-p-153-komplett.pdf",
    DATA_DIR / "lni169/lni-p-169-komplett.pdf",
    DATA_DIR / "lni188/lni-p-188-komplett.pdf",
    DATA_DIR / "lni207/lni-p-207-komplett.pdf",
    DATA_DIR / "lni218/lni-p-218-komplett.pdf",
    DATA_DIR / "lni233/lni-p-233-komplett.pdf",
    DATA_DIR / "lni247/lni-p-247-komplett.pdf",
    DATA_DIR / "lni262/lni-p-262-komplett.pdf",
    DATA_DIR / "lni273/lni-p-273-komplett.pdf",
    DATA_DIR / "lni284/proceedings_complete.pdf",
    DATA_DIR / "lni297/DELFI2019_Tagungsband_komplett.pdf",
    DATA_DIR / "lni297/DELFI2019_Tagungsband_komplett_Onlineversion.pdf",
    DATA_DIR / "lni308/DELFI2020_Proceedings_komplett.pdf",
    DATA_DIR / "lni316/DELFI_2021-Proceedings.pdf",
    DATA_DIR / "lni322/DELFI_2022_Proceedings_FINAL.pdf",
    DATA_DIR / "lni338/Komplettband.pdf",
    DATA_DIR / "lni356/DELFI_2024_ProceedingsComplete_alt.pdf",
    DATA_DIR / "lni356/DELFI_2024_ProceedingsComplete.pdf",
    DATA_DIR / "lni356/proceedings.pdf",
    DATA_DIR / "lni369/DELFI2025_ProceedingsComplete.pdf",
}

# Terms to exclude (covers, prefaces, etc.)
EXCLUSION_TERMS = ["cover", "vorwort", "preface", "foreword"]


def should_exclude_pdf(pdf_path: Path) -> bool:
    """
    Check if PDF should be excluded from annotation.
    
    Excludes:
    - Full proceedings (from manual set)
    - Covers, prefaces, forewords (by filename keyword)
    
    Returns:
        True if PDF should be excluded, False otherwise
    """
    # Check manual exclusion set
    if pdf_path in FULL_PROCEEDINGS_SET:
        return True
    
    # Check filename keywords (case-insensitive)
    filename_lower = pdf_path.name.lower()
    if any(term in filename_lower for term in EXCLUSION_TERMS):
        return True
    
    return False


def get_all_relevant_pdfs() -> list[tuple[Path, str, int]]:
    """
    Get all relevant PDF files for annotation.
    
    Returns:
        List of tuples: (pdf_path, lni_folder, year)
    """
    pdf_list = []
    
    for folder in sorted(DATA_DIR.iterdir()):
        if folder.is_dir() and folder.name.startswith("lni"):
            lni_folder = folder.name
            year = LNI_MAPPING.get(lni_folder)
            
            if year is None:
                print(f"WARNING: Unknown LNI folder '{lni_folder}', skipping...")
                continue
            
            for pdf_path in sorted(folder.glob("*.pdf")):
                if not should_exclude_pdf(pdf_path):
                    pdf_list.append((pdf_path, lni_folder, year))
    
    return pdf_list



# =============================================================================
# 3) CLASSIFICATION FUNCTION
# =============================================================================




def classify_pdf(
    client: OpenAI,
    pdf_path: Path,
    model: str,
    temperature: float
) -> dict:
    """
    Classify a single DeLFI paper for research software, evaluation, and empirical study.
    
    Args:
        client: OpenAI client instance
        pdf_path: Path to the PDF file
        model: OpenAI model to use (e.g., "gpt-4o-mini")
        temperature: Temperature for generation (0 for reproducibility)
    
    Returns:
        Dict with keys:
        - 'label_research_software' (0 or 1)
        - 'label_research_software_justification' (str)
        - 'label_software_evaluation' (0 or 1)
        - 'label_software_evaluation_justification' (str)
        - 'label_empirical_study' (0 or 1)
        - 'label_empirical_study_justification' (str)
        Or dict with 'error' key if classification failed
    """
    # Encode PDF as base64
    with open(pdf_path, "rb") as f:
        pdf_data = base64.b64encode(f.read()).decode("utf-8")
    
    # Call API with structured output
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": "You are an expert in classifying scientific journal articles. You will classify articles based on three criteria: research software presence, research software evaluation, and empirical study methodology."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {
                            "filename": pdf_path.name,
                            "file_data": f"data:application/pdf;base64,{pdf_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Classify this scientific journal article on three dimensions: "

                        "1. Research Software (label_research_software): Does the article contain research software? Research software includes source code files, algorithms, scripts, computational workflows and executables that were created during the research process or for a research purpose. (0 = contains no research software, 1 = contains research software)"
                        
                        "2. Software Evaluation (label_software_evaluation): Does the article evaluate the research software? A key focus is, whether the quality characteristics of the software are evaluated. (0 = no evaluation, 1 = evaluates software)"

                        "3. Empirical Study (label_empirical_study): Is the article an empirical study where software serves as a means to conduct empirical research? Empirical research includes:"
                        "- hypothesis-testing empirical research with largely standardized steps and rules in the research process and the use of statistical methods"
                        "- descriptive empirical research with common steps and rules in the research process and the use of diverse analysis methods, including in the field"
                        "- intervening empirical research with variable steps and rules in the research process and the use of diverse analysis methods, including in the field"
                        
                        "(0 = not an empirical study, 1 = is an empirical study)"

                        "For each classification, briefly explain your decision."
                    }
                ]
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": JSON_SCHEMA_CONFIG
        }
    )
    
    return json.loads(response.choices[0].message.content)

def classify_pdf_with_retry(
    client: OpenAI,
    pdf_path: Path,
    model: str,
    temperature: float,
    max_retries: int = MAX_RETRIES
) -> dict:
    """
    Classify PDF with retry logic and validation.
    
    Returns:
        Dict with 'label_research_software', 'label_justification', and 'status' keys
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            result = classify_pdf(client, pdf_path, model, temperature)
            
            # Validate response structure
            if "label_research_software" not in result:
                print(f"  WARNING: Missing 'label_research_software' in response for {pdf_path.name}")
                result["label_research_software"] = None
            
            if "label_research_software_justification" not in result:
                print(f"  WARNING: Missing 'label_research_software_justification' in response for {pdf_path.name}")
                result["label_research_software_justification"] = None

            if "label_software_evaluation" not in result:
                print(f"  WARNING: Missing 'label_software_evaluation' in response for {pdf_path.name}")
                result["label_software_evaluation"] = None

            if "label_software_evaluation_justification" not in result:
                print(f"  WARNING: Missing 'label_software_evaluation_justification' in response for {pdf_path.name}")
                result["label_software_evaluation_justification"] = None

            if "label_empirical_study" not in result:
                print(f"  WARNING: Missing 'label_empirical_study' in response for {pdf_path.name}")
                result["label_empirical_study"] = None

            if "label_empirical_study_justification" not in result:
                print(f"  WARNING: Missing 'label_empirical_study_justification' in response for {pdf_path.name}")
                result["label_empirical_study_justification"] = None
            
            # Validate binary values
            if result["label_research_software"] not in [0, 1, None]:
                print(f"  WARNING: Invalid 'label_research_software' value: {result['label_research_software']} for {pdf_path.name}")
                result["label_research_software"] = None

            if result["label_software_evaluation"] not in [0, 1, None]:
                print(f"  WARNING: Invalid 'label_software_evaluation' value: {result['label_software_evaluation']} for {pdf_path.name}")
                result["label_software_evaluation"] = None

            if result["label_empirical_study"] not in [0, 1, None]:
                print(f"  WARNING: Invalid 'label_empirical_study' value: {result['label_empirical_study']} for {pdf_path.name}")
                result["label_empirical_study"] = None
            
            result["status"] = "success"
            return result
            
        except Exception as e:
            last_error = str(e)
            print(f"  ERROR (attempt {attempt + 1}/{max_retries}): {pdf_path.name} - {last_error}")
            
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY_SECONDS)
    
    # All retries failed
    return {
        "label_research_software": None,
        "label_research_software_justification": None,
        "label_software_evaluation": None,
        "label_software_evaluation_justification": None,
        "label_empirical_study": None,
        "label_empirical_study_justification": None,
        "status": f"failed: {last_error}"
    }


# =============================================================================
# 4) MAIN PROCESSING LOOP
# =============================================================================

def process_pdfs(
    pdf_list: list[tuple[Path, str, int]],
    model: str,
    temperature: float,
    checkpoint_path: Path | None = None,
    test_mode: bool = False,
    test_sample_size: int = 50
) -> pd.DataFrame:
    """
    Process all PDFs and return results as DataFrame.
    
    Args:
        pdf_list: List of (pdf_path, lni_folder, year) tuples
        model: OpenAI model to use
        temperature: Temperature for generation
        checkpoint_path: Path to existing checkpoint to resume from (optional)
        test_mode: If True, only process a random sample
        test_sample_size: Number of samples for test mode
    
    Returns:
        DataFrame with annotation results
    """
    # Initialize OpenAI client
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    client = OpenAI(api_key=openai_api_key)
    
    # Create results directory
    RESULTS_DIR.mkdir(exist_ok=True)
    
    # Load existing checkpoint if provided
    processed_files = set()
    results = []
    
    if checkpoint_path and checkpoint_path.exists():
        print(f"Resuming from checkpoint: {checkpoint_path}")
        checkpoint_df = pd.read_csv(checkpoint_path)
        results = checkpoint_df.to_dict("records")
        processed_files = set(checkpoint_df["filename"].tolist())
        print(f"  Loaded {len(processed_files)} already processed files")
    
    # Filter out already processed files
    pdfs_to_process = [
        (path, lni, year) for path, lni, year in pdf_list
        if path.name not in processed_files
    ]
    
    # Test mode: random sample
    if test_mode:
        if len(pdfs_to_process) > test_sample_size:
            print(f"\nTEST MODE: Sampling {test_sample_size} random PDFs from {len(pdfs_to_process)} remaining")
            random.seed(RANDOM_SEED) # For reproducability 
            pdfs_to_process = random.sample(pdfs_to_process, test_sample_size)
        else:
            print(f"\nTEST MODE: Processing all {len(pdfs_to_process)} remaining PDFs (less than sample size)")
    
    print(f"\nProcessing {len(pdfs_to_process)} PDFs...")
    print(f"Model: {model}, Temperature: {temperature}")
    print(f"Checkpoint every {CHECKPOINT_FREQUENCY} files")
    print(f"Circuit breaker: {MAX_CONSECUTIVE_ERRORS} consecutive errors\n")
    
    # Generate checkpoint filename for this run (with hour-minute for uniqueness)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    checkpoint_filename = f"checkpoint_{model}_{timestamp}.csv"
    current_checkpoint_path = RESULTS_DIR / checkpoint_filename
    
    # Processing counters
    consecutive_errors = 0
    processed_count = 0
    
    # Main processing loop with progress bar
    with tqdm(pdfs_to_process, desc="Annotating PDFs", unit="pdf") as pbar:
        for pdf_path, lni_folder, year in pbar:
            # Update progress bar description
            pbar.set_postfix_str(f"{pdf_path.name[:30]}...")
            
            # Classify the PDF
            result = classify_pdf_with_retry(client, pdf_path, model, temperature)
            
            # Build result record
            record = {
                "lni_edition": lni_folder,
                "year": year,
                "filename": pdf_path.name,
                "label_research_software": result["label_research_software"],
                "label_research_software_justification": result["label_research_software_justification"],
                "label_software_evaluation": result["label_software_evaluation"],
                "label_software_evaluation_justification": result["label_software_evaluation_justification"],
                "label_empirical_study": result["label_empirical_study"],
                "label_empirical_study_justification": result["label_empirical_study_justification"],
                "status": result["status"]
            }
            results.append(record)
            processed_count += 1
            
            # Track consecutive errors for circuit breaker
            if result["status"] != "success":
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print(f"\n\nCIRCUIT BREAKER: {MAX_CONSECUTIVE_ERRORS} consecutive errors reached!")
                    print("Stopping processing. Check your API key, network, or the PDF files.")
                    print(f"Saving checkpoint before exit...\n")
                    break
            else:
                consecutive_errors = 0  # Reset on success
            
            # Save checkpoint periodically
            if processed_count % CHECKPOINT_FREQUENCY == 0:
                checkpoint_df = pd.DataFrame(results)
                checkpoint_df.to_csv(current_checkpoint_path, index=False)
                tqdm.write(f"  [Checkpoint saved: {len(results)} records -> {current_checkpoint_path}]")
    
    # Final save
    final_df = pd.DataFrame(results)
    
    # Save checkpoint one more time (in case we didn't hit a checkpoint interval)
    final_df.to_csv(current_checkpoint_path, index=False)
    print(f"\nFinal checkpoint saved: {current_checkpoint_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = len(results) - success_count
    print(f"Total processed: {len(results)}")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {failed_count}")
    
    if failed_count > 0:
        print("\nFailed files:")
        for r in results:
            if r["status"] != "success":
                print(f"  - {r['filename']}: {r['status']}")
    
    return final_df



# =============================================================================
# 5) RESULTS SAVING
# =============================================================================

def save_final_results(df: pd.DataFrame, model: str, test_mode: bool = False) -> Path:
    """
    Save final results DataFrame to CSV.
    
    Naming convention: df_{model}_{date}.csv
    Test mode adds '_TEST' suffix.
    
    Args:
        df: Results DataFrame
        model: Model name used for annotation
        test_mode: Whether this was a test run
    
    Returns:
        Path to saved CSV file
    """
    # Create results directory if needed
    RESULTS_DIR.mkdir(exist_ok=True)
    
    # Generate filename (with hour-minute for uniqueness)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    suffix = "_TEST" if test_mode else ""
    filename = f"df_{model}_{timestamp}{suffix}.csv"
    filepath = RESULTS_DIR / filename
    
    # Save DataFrame
    df.to_csv(filepath, index=False)
    
    print(f"\nResults saved to: {filepath}")
    print(f"  Total records: {len(df)}")
    
    # Print label distribution
    if "label_research_software" in df.columns:
        label_counts = df["label_research_software"].value_counts(dropna=False)
        print(f"\nLabel distribution:")
        for label, count in sorted(label_counts.items(), key=lambda x: (x[0] is None, x[0])):
            label_name = {0: "No research software", 1: "Contains research software", None: "Failed/Missing"}.get(label, label)
            pct = count / len(df) * 100
            print(f"  {label_name}: {count} ({pct:.1f}%)")
    
    return filepath


def print_yearly_summary(df: pd.DataFrame) -> None:
    """
    Print summary statistics grouped by year.
    
    Shows: count, mean label, std for each year.
    """
    print("\n" + "=" * 70)
    print("YEARLY SUMMARY (for visualization prep)")
    print("=" * 70)
    
    # Filter to successful annotations only
    df_valid = df[df["label_research_software"].notna()].copy()
    
    if len(df_valid) == 0:
        print("No valid annotations to summarize.")
        return
    
    # Group by year
    yearly_stats = df_valid.groupby("year").agg(
        n_papers=("label_research_software", "count"),
        mean_label=("label_research_software", "mean"),
        std_label=("label_research_software", "std"),
        sum_research_sw=("label_research_software", "sum")
    ).round(3)
    
    print(f"\n{'Year':<6} {'Papers':<8} {'With RS':<10} {'Mean':<8} {'Std':<8}")
    print("-" * 50)
    
    for year, row in yearly_stats.iterrows():
        std_str = f"{row['std_label']:.3f}" if pd.notna(row['std_label']) else "N/A"
        print(f"{year:<6} {int(row['n_papers']):<8} {int(row['sum_research_sw']):<10} {row['mean_label']:.3f}    {std_str}")
    
    print("-" * 50)
    total = len(df_valid)
    total_rs = int(df_valid["label_research_software"].sum())
    overall_mean = df_valid["label_research_software"].mean()
    overall_std = df_valid["label_research_software"].std()
    print(f"{'TOTAL':<6} {total:<8} {total_rs:<10} {overall_mean:.3f}    {overall_std:.3f}")



# =============================================================================
#  6) COMMAND-LINE INTERFACE
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Annotate DeLFI journal articles for research software using OpenAI API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test mode with 50 random samples (default model: gpt-4o-mini)
  python llm_annotation_research_software.py --test
  
  # Test mode with custom sample size
  python llm_annotation_research_software.py --test --test-size 100
  
  # Full run with default settings
  python llm_annotation_research_software.py
  
  # Full run with specific model
  python llm_annotation_research_software.py --model gpt-4o
  
  # Resume from checkpoint
  python llm_annotation_research_software.py --resume results/checkpoint_gpt-4o-mini_2026-01-21.csv
  
  # Combine options
  python llm_annotation_research_software.py --model gpt-4o --temperature 0.1 --resume results/checkpoint.csv
        """
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"OpenAI model to use (default: {DEFAULT_MODEL})"
    )
    
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help=f"Temperature for generation, 0 for reproducibility (default: {DEFAULT_TEMPERATURE})"
    )
    
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode with random sample of PDFs"
    )
    
    parser.add_argument(
        "--test-size",
        type=int,
        default=50,
        help="Number of PDFs to sample in test mode (default: 50)"
    )
    
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Path to checkpoint CSV file to resume from"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making API calls"
    )
    
    return parser.parse_args()



# =============================================================================
# 7) MAIN ENTRY POINT
# =============================================================================

def main():
    """
    Main entry point for the annotation script.
    """
    # Parse command-line arguments
    args = parse_arguments()
    
    # Print banner
    print("\n" + "=" * 70)
    print("DeLFI Research Software Annotation")
    print("=" * 70)
    print(f"Model:       {args.model}")
    print(f"Temperature: {args.temperature}")
    print(f"Test mode:   {args.test}" + (f" (sample size: {args.test_size})" if args.test else ""))
    print(f"Resume from: {args.resume if args.resume else 'None (fresh start)'}")
    print("=" * 70)
    
    # Get all relevant PDFs
    print("\nScanning for PDF files...")
    pdf_list = get_all_relevant_pdfs()
    print(f"Found {len(pdf_list)} relevant PDFs (after exclusions)")
    
    # Dry run mode - just show what would be processed
    if args.dry_run:
        print("\n[DRY RUN - No API calls will be made]\n")
        
        # Show distribution by year
        year_counts = {}
        for _, _, year in pdf_list:
            year_counts[year] = year_counts.get(year, 0) + 1
        
        print(f"{'Year':<6} {'PDFs':<8}")
        print("-" * 20)
        for year in sorted(year_counts.keys()):
            print(f"{year:<6} {year_counts[year]:<8}")
        print("-" * 20)
        print(f"{'TOTAL':<6} {len(pdf_list):<8}")
        
        # Show sample of files
        print("\nSample of files to process:")
        for pdf_path, lni, year in pdf_list[:10]:
            print(f"  [{lni}] {pdf_path.name}")
        if len(pdf_list) > 10:
            print(f"  ... and {len(pdf_list) - 10} more")
        
        return
    
    # Confirm before full run (not in test mode)
    if not args.test and not args.resume:
        print(f"\nAbout to process {len(pdf_list)} PDFs.")
        print("Estimated time: ~2 hours")
        response = input("\nProceed? [y/N]: ").strip().lower()
        if response != "y":
            print("Aborted.")
            return
    
    # Process PDFs
    checkpoint_path = Path(args.resume) if args.resume else None
    
    results_df = process_pdfs(
        pdf_list=pdf_list,
        model=args.model,
        temperature=args.temperature,
        checkpoint_path=checkpoint_path,
        test_mode=args.test,
        test_sample_size=args.test_size
    )
    
    # Save final results
    final_path = save_final_results(
        df=results_df,
        model=args.model,
        test_mode=args.test
    )
    
    # Print yearly summary
    #print_yearly_summary(results_df)
    
    print("\n" + "=" * 70)
    print("ANNOTATION COMPLETE")
    print("=" * 70)
    print(f"Results saved to: {final_path}")


if __name__ == "__main__":
    main()
