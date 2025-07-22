"""
Few-shot examples management utility
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..core.logger import app_logger


class FewShotManager:
    """Utility class for managing few-shot examples"""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data"
        self.json_file = self.data_dir / "few_shot_examples.json"
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """Ensure data directory exists"""
        self.data_dir.mkdir(exist_ok=True)
    
    def load_examples(self) -> Dict[str, Any]:
        """Load examples from JSON file"""
        try:
            if not self.json_file.exists():
                return {"examples": [], "categories": {}}
            
            with open(self.json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            app_logger.error(f"Error loading examples: {str(e)}")
            return {"examples": [], "categories": {}}
    
    def save_examples(self, data: Dict[str, Any]) -> bool:
        """Save examples to JSON file"""
        try:
            # Add metadata
            data["metadata"] = {
                "last_updated": datetime.now().isoformat(),
                "total_examples": len(data.get("examples", [])),
                "version": "1.0"
            }
            
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            app_logger.info(f"Saved {len(data.get('examples', []))} examples to JSON file")
            return True
        except Exception as e:
            app_logger.error(f"Error saving examples: {str(e)}")
            return False
    
    def add_example(self, question: str, answer: str, category: str = "general", 
                    keywords: List[str] = None, context: Dict[str, Any] = None) -> bool:
        """Add a new example"""
        
        data = self.load_examples()
        
        new_example = {
            "question": question.strip(),
            "answer": answer.strip(),
            "category": category,
            "keywords": keywords or [],
            "context": context or {},
            "created_at": datetime.now().isoformat()
        }
        
        data["examples"].append(new_example)
        
        # Update category info if it doesn't exist
        if category not in data.get("categories", {}):
            data.setdefault("categories", {})[category] = {
                "name": category.title(),
                "description": f"Perguntas sobre {category}"
            }
        
        return self.save_examples(data)
    
    def update_example(self, index: int, question: str = None, answer: str = None, 
                      category: str = None, keywords: List[str] = None, 
                      context: Dict[str, Any] = None) -> bool:
        """Update an existing example"""
        
        data = self.load_examples()
        examples = data.get("examples", [])
        
        if index < 0 or index >= len(examples):
            app_logger.error(f"Invalid example index: {index}")
            return False
        
        example = examples[index]
        
        if question is not None:
            example["question"] = question.strip()
        if answer is not None:
            example["answer"] = answer.strip()
        if category is not None:
            example["category"] = category
        if keywords is not None:
            example["keywords"] = keywords
        if context is not None:
            example["context"] = context
        
        example["updated_at"] = datetime.now().isoformat()
        
        return self.save_examples(data)
    
    def delete_example(self, index: int) -> bool:
        """Delete an example"""
        
        data = self.load_examples()
        examples = data.get("examples", [])
        
        if index < 0 or index >= len(examples):
            app_logger.error(f"Invalid example index: {index}")
            return False
        
        deleted_example = examples.pop(index)
        app_logger.info(f"Deleted example: {deleted_example['question'][:50]}...")
        
        return self.save_examples(data)
    
    def get_examples_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all examples from a specific category"""
        
        data = self.load_examples()
        examples = data.get("examples", [])
        
        return [ex for ex in examples if ex.get("category") == category]
    
    def search_examples(self, query: str) -> List[Dict[str, Any]]:
        """Search examples by question or keywords"""
        
        data = self.load_examples()
        examples = data.get("examples", [])
        query_lower = query.lower()
        
        matching_examples = []
        
        for example in examples:
            # Search in question
            if query_lower in example.get("question", "").lower():
                matching_examples.append(example)
                continue
            
            # Search in keywords
            keywords = example.get("keywords", [])
            if any(query_lower in keyword.lower() for keyword in keywords):
                matching_examples.append(example)
                continue
            
            # Search in answer
            if query_lower in example.get("answer", "").lower():
                matching_examples.append(example)
        
        return matching_examples
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the examples"""
        
        data = self.load_examples()
        examples = data.get("examples", [])
        
        if not examples:
            return {"total": 0, "categories": {}}
        
        stats = {
            "total": len(examples),
            "categories": {},
            "average_question_length": 0,
            "average_answer_length": 0,
            "keywords_count": 0
        }
        
        question_lengths = []
        answer_lengths = []
        total_keywords = 0
        
        for example in examples:
            category = example.get("category", "general")
            if category not in stats["categories"]:
                stats["categories"][category] = 0
            stats["categories"][category] += 1
            
            question_lengths.append(len(example.get("question", "")))
            answer_lengths.append(len(example.get("answer", "")))
            total_keywords += len(example.get("keywords", []))
        
        if question_lengths:
            stats["average_question_length"] = sum(question_lengths) / len(question_lengths)
        if answer_lengths:
            stats["average_answer_length"] = sum(answer_lengths) / len(answer_lengths)
        
        stats["keywords_count"] = total_keywords
        stats["average_keywords_per_example"] = total_keywords / len(examples) if examples else 0
        
        return stats
    
    def export_to_csv(self, filename: str = None) -> str:
        """Export examples to CSV format"""
        
        if filename is None:
            filename = f"kumon_examples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        data = self.load_examples()
        examples = data.get("examples", [])
        
        csv_content = "Category,Question,Answer,Keywords\n"
        
        for example in examples:
            category = example.get("category", "")
            question = example.get("question", "").replace('"', '""')
            answer = example.get("answer", "").replace('"', '""')
            keywords = "|".join(example.get("keywords", []))
            
            csv_content += f'"{category}","{question}","{answer}","{keywords}"\n'
        
        filepath = self.data_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(csv_content)
            
            app_logger.info(f"Exported examples to CSV: {filepath}")
            return str(filepath)
        except Exception as e:
            app_logger.error(f"Error exporting to CSV: {str(e)}")
            return ""
    
    def import_from_csv(self, filepath: str) -> bool:
        """Import examples from CSV file"""
        
        try:
            import csv
            
            data = self.load_examples()
            imported_count = 0
            
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    keywords = row.get("Keywords", "").split("|") if row.get("Keywords") else []
                    keywords = [k.strip() for k in keywords if k.strip()]
                    
                    new_example = {
                        "question": row.get("Question", "").strip(),
                        "answer": row.get("Answer", "").strip(),
                        "category": row.get("Category", "general").strip(),
                        "keywords": keywords,
                        "context": {},
                        "imported_at": datetime.now().isoformat()
                    }
                    
                    if new_example["question"] and new_example["answer"]:
                        data["examples"].append(new_example)
                        imported_count += 1
            
            if imported_count > 0:
                success = self.save_examples(data)
                if success:
                    app_logger.info(f"Imported {imported_count} examples from CSV")
                return success
            else:
                app_logger.warning("No valid examples found in CSV file")
                return False
                
        except Exception as e:
            app_logger.error(f"Error importing from CSV: {str(e)}")
            return False
    
    def backup_examples(self) -> str:
        """Create a backup of current examples"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"few_shot_examples_backup_{timestamp}.json"
        backup_path = self.data_dir / backup_filename
        
        try:
            data = self.load_examples()
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            app_logger.info(f"Created backup: {backup_path}")
            return str(backup_path)
        except Exception as e:
            app_logger.error(f"Error creating backup: {str(e)}")
            return ""
    
    def validate_examples(self) -> List[Dict[str, Any]]:
        """Validate examples and return issues found"""
        
        data = self.load_examples()
        examples = data.get("examples", [])
        issues = []
        
        for i, example in enumerate(examples):
            issue = {"index": i, "problems": []}
            
            # Check required fields
            if not example.get("question", "").strip():
                issue["problems"].append("Missing or empty question")
            
            if not example.get("answer", "").strip():
                issue["problems"].append("Missing or empty answer")
            
            if not example.get("category", "").strip():
                issue["problems"].append("Missing or empty category")
            
            # Check lengths
            question = example.get("question", "")
            if len(question) < 10:
                issue["problems"].append("Question too short (< 10 characters)")
            elif len(question) > 500:
                issue["problems"].append("Question too long (> 500 characters)")
            
            answer = example.get("answer", "")
            if len(answer) < 20:
                issue["problems"].append("Answer too short (< 20 characters)")
            elif len(answer) > 1000:
                issue["problems"].append("Answer too long (> 1000 characters)")
            
            # Check keywords
            keywords = example.get("keywords", [])
            if not keywords:
                issue["problems"].append("No keywords provided")
            elif len(keywords) > 10:
                issue["problems"].append("Too many keywords (> 10)")
            
            if issue["problems"]:
                issues.append(issue)
        
        return issues 