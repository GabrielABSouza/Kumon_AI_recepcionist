#!/usr/bin/env python3
"""
PyTorch + Sentence Transformers validation script for Railway deployment
Tests that PyTorch CPU installation works correctly with sentence-transformers
"""

def validate_pytorch_installation():
    """Validate PyTorch CPU installation and device detection"""
    print("🔍 Validating PyTorch installation...")
    
    try:
        import torch
        print(f"✅ PyTorch version: {torch.__version__}")
        print(f"✅ PyTorch installation path: {torch.__file__}")
        
        # Test device detection
        if torch.cuda.is_available():
            device = "cuda"
            print(f"⚡ CUDA available: {torch.cuda.device_count()} device(s)")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = "mps"  
            print("⚡ MPS (Metal) available")
        else:
            device = "cpu"
            print("⚡ Using CPU device (Railway deployment ready)")
        
        # Test tensor operations
        test_tensor = torch.randn(2, 3, device=device)
        print(f"✅ Tensor operations working: {test_tensor.shape} on {device}")
        
        return True, device
        
    except ImportError as e:
        print(f"❌ PyTorch import failed: {e}")
        return False, None
    except Exception as e:
        print(f"❌ PyTorch validation failed: {e}")
        return False, None

def validate_sentence_transformers():
    """Validate sentence-transformers with PyTorch backend"""
    print("\n🔍 Validating Sentence Transformers...")
    
    try:
        from sentence_transformers import SentenceTransformer
        print("✅ Sentence Transformers imported successfully")
        
        # Test model loading (use a small model for validation)
        model_name = "sentence-transformers/all-MiniLM-L6-v2"  # Lightweight model
        print(f"🔄 Loading test model: {model_name}")
        
        model = SentenceTransformer(model_name, device="cpu")
        print(f"✅ Model loaded successfully on CPU")
        
        # Test embedding generation
        test_text = "This is a test sentence for embedding validation."
        embeddings = model.encode([test_text])
        print(f"✅ Embedding generated: shape={embeddings.shape}, dtype={embeddings.dtype}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Sentence Transformers import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Sentence Transformers validation failed: {e}")
        return False

def validate_kumon_model():
    """Validate the specific model used by Kumon Assistant"""
    print("\n🔍 Validating Kumon-specific model...")
    
    try:
        from sentence_transformers import SentenceTransformer
        
        # Use the actual model from config
        kumon_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        print(f"🔄 Loading Kumon model: {kumon_model}")
        
        model = SentenceTransformer(kumon_model, device="cpu")
        print(f"✅ Kumon model loaded successfully on CPU")
        
        # Test with Portuguese/multilingual text
        test_texts = [
            "Bem-vindo ao Kumon!",
            "Como posso ajudar você hoje?", 
            "Exercícios de matemática para crianças"
        ]
        
        embeddings = model.encode(test_texts)
        print(f"✅ Multilingual embeddings generated: {len(test_texts)} texts → {embeddings.shape}")
        
        return True
        
    except Exception as e:
        print(f"❌ Kumon model validation failed: {e}")
        return False

def main():
    """Run complete validation suite"""
    print("🚀 PYTORCH + SENTENCE-TRANSFORMERS VALIDATION")
    print("=" * 50)
    
    # Step 1: PyTorch validation
    pytorch_ok, device = validate_pytorch_installation()
    if not pytorch_ok:
        print("\n❌ VALIDATION FAILED: PyTorch not working")
        return False
    
    # Step 2: Sentence Transformers validation  
    st_ok = validate_sentence_transformers()
    if not st_ok:
        print("\n❌ VALIDATION FAILED: Sentence Transformers not working")
        return False
    
    # Step 3: Kumon-specific model validation
    kumon_ok = validate_kumon_model()
    if not kumon_ok:
        print("\n⚠️  WARNING: Kumon model failed, but basic functionality works")
    
    print("\n" + "=" * 50)
    print("✅ VALIDATION COMPLETE")
    print(f"✅ PyTorch {torch.__version__} working on {device}")
    print("✅ Sentence Transformers working")
    print("✅ Ready for Railway deployment")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)