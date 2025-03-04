
"""
Storage module for LLM operation data.

This module handles the storage and retrieval of collected data about LLM operations,
using Polars dataframes to efficiently store and query operational data in JSON format.
"""

import os
import json
import polars as pl
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from aicore.observability.collector import LlmOperationRecord
from aicore.const import DEFAULT_OBSERVABILITY_DIR, DEFAULT_OBSERVABILITY_FILE, MAX_STORED_RESPONSE_LENGTH

class OperationStorage:
    """
    Handles storage and retrieval of LLM operation data.
    
    This class provides functionality to store operation records in JSON format using
    Polars dataframes, with methods to append new records, load existing data, and
    perform basic queries.
    """
    
    def __init__(self, storage_dir: Optional[str] = None, storage_file: Optional[str] = None):
        """
        Initialize the storage system.
        
        Args:
            storage_dir: Directory where data will be stored (default: "observability_data")
            storage_file: Filename for the storage file (default: "llm_operations.json")
        """
        self.storage_dir = Path(storage_dir or DEFAULT_OBSERVABILITY_DIR)
        self.storage_file = Path(self.storage_dir) / (storage_file or DEFAULT_OBSERVABILITY_FILE)
        self._ensure_storage_dir()
        self._dataframe = None
        
    def _ensure_storage_dir(self):
        """Ensure the storage directory exists."""
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def store_record(self, record: LlmOperationRecord):
        """
        Store a single operation record.
        
        Args:
            record: LlmOperationRecord to store
        """
        # Convert record to dict
        record_dict = record.model_dump()
        
        # Truncate response if it's too long
        if record_dict.get("response") and isinstance(record_dict["response"], str) and len(record_dict["response"]) > MAX_STORED_RESPONSE_LENGTH:
            record_dict["response"] = record_dict["response"][:MAX_STORED_RESPONSE_LENGTH] + "... [truncated]"
        
        # Load existing data if available
        if self._dataframe is None:
            self._load_dataframe()
        
        # Create a new dataframe with the record
        new_row = pl.DataFrame([record_dict])
        
        # Append to existing dataframe
        if self._dataframe is None:
            self._dataframe = new_row
        else:
            self._dataframe = pl.concat([self._dataframe, new_row])
        
        # Save to file
        self._save_dataframe()
    
    def _load_dataframe(self):
        """Load the dataframe from storage file if it exists."""
        if not self.storage_file.exists():
            self._dataframe = None
            return
        
        try:
            # Load the JSON file as a list of records
            with open(self.storage_file, 'r') as f:
                records = json.load(f)
            
            # Create dataframe from records
            if records:
                self._dataframe = pl.DataFrame(records)
            else:
                self._dataframe = None
        except (json.JSONDecodeError, pl.exceptions.PolarsError) as e:
            # Handle corrupted file
            print(f"Error loading operation data: {e}")
            self._dataframe = None
    
    def _save_dataframe(self):
        """Save the dataframe to the storage file."""
        if self._dataframe is None:
            return
        
        # Convert to records and save as JSON
        records = self._dataframe.to_dicts()
        with open(self.storage_file, 'w') as f:
            json.dump(records, f, indent=2)
    
    def get_all_records(self) -> pl.DataFrame:
        """
        Get all stored operation records as a Polars DataFrame.
        
        Returns:
            Polars DataFrame containing all records
        """
        if self._dataframe is None:
            self._load_dataframe()
        
        return self._dataframe or pl.DataFrame()
    
    def query_records(self, filters: Dict[str, Any] = None, start_date: str = None, 
                     end_date: str = None, limit: int = None) -> pl.DataFrame:
        """
        Query records with optional filtering.
        
        Args:
            filters: Dictionary of column name to value for filtering
            start_date: Start date for timestamp filtering (ISO format)
            end_date: End date for timestamp filtering (ISO format)
            limit: Maximum number of records to return
            
        Returns:
            Filtered Polars DataFrame
        """
        if self._dataframe is None:
            self._load_dataframe()
            
        if self._dataframe is None:
            return pl.DataFrame()
        
        result = self._dataframe
        
        # Apply filters
        if filters:
            for col, value in filters.items():
                if col in result.columns:
                    if isinstance(value, list):
                        result = result.filter(pl.col(col).is_in(value))
                    else:
                        result = result.filter(pl.col(col) == value)
        
        # Apply date range filter
        if start_date and 'timestamp' in result.columns:
            result = result.filter(pl.col('timestamp') >= start_date)
        if end_date and 'timestamp' in result.columns:
            result = result.filter(pl.col('timestamp') <= end_date)
            
        # Apply limit
        if limit and limit > 0:
            result = result.limit(limit)
            
        return result
    
    def get_summary_metrics(self) -> Dict[str, Any]:
        """
        Calculate summary metrics from the stored records.
        
        Returns:
            Dictionary with summary metrics including total operations, average latency,
            success rate, and token usage statistics
        """
        df = self.get_all_records()
        
        if df.is_empty():
            return {
                "total_operations": 0,
                "avg_latency_ms": 0,
                "success_rate": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "providers": [],
                "models": []
            }
        
        # Calculate metrics
        total_operations = df.height
        avg_latency = df.select(pl.mean("latency_ms")).item()
        success_rate = df.select(pl.mean(pl.col("success").cast(pl.Int32))).item() * 100
        
        # Token usage (excluding nulls)
        total_input_tokens = df.filter(pl.col("input_tokens").is_not_null()).select(pl.sum("input_tokens")).item()
        total_output_tokens = df.filter(pl.col("output_tokens").is_not_null()).select(pl.sum("output_tokens")).item()
        
        # Unique providers and models
        providers = df.select(pl.col("provider").unique()).to_series().to_list()
        models = df.select(pl.col("model").unique()).to_series().to_list()
        
        return {
            "total_operations": total_operations or 0,
            "avg_latency_ms": float(avg_latency) if avg_latency is not None else 0,
            "success_rate": float(success_rate) if success_rate is not None else 0,
            "total_input_tokens": int(total_input_tokens) if total_input_tokens is not None else 0,
            "total_output_tokens": int(total_output_tokens) if total_output_tokens is not None else 0,
            "providers": providers,
            "models": models
        }
    
    def clear_older_than(self, date_str: str) -> int:
        """
        Remove records older than the specified date.
        
        Args:
            date_str: Date in ISO format (YYYY-MM-DD)
            
        Returns:
            Number of records removed
        """
        if self._dataframe is None:
            self._load_dataframe()
            
        if self._dataframe is None or 'timestamp' not in self._dataframe.columns:
            return 0
            
        original_count = self._dataframe.height
        self._dataframe = self._dataframe.filter(pl.col('timestamp') >= date_str)
        removed_count = original_count - self._dataframe.height
        
        # Save updated dataframe
        if removed_count > 0:
            self._save_dataframe()
            
        return removed_count
    
    def get_operation_details(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific operation.
        
        Args:
            operation_id: Unique identifier for the operation
            
        Returns:
            Dictionary with operation details or None if not found
        """
        if self._dataframe is None:
            self._load_dataframe()
            
        if self._dataframe is None or 'operation_id' not in self._dataframe.columns:
            return None
            
        matching_records = self._dataframe.filter(pl.col('operation_id') == operation_id)
        
        if matching_records.is_empty():
            return None
            
        # Convert first matching record to dict
        return matching_records.row(0, named=True)
    
    def export_to_csv(self, file_path: str) -> bool:
        """
        Export all records to a CSV file.
        
        Args:
            file_path: Path where the CSV file will be saved
            
        Returns:
            True if export was successful, False otherwise
        """
        if self._dataframe is None:
            self._load_dataframe()
            
        if self._dataframe is None:
            return False
            
        try:
            self._dataframe.write_csv(file_path)
            return True
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return False