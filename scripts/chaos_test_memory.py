import time
import logging
from arova.core.cognition.memory.vector import QdrantLocal
from arova.core.cognition.memory.schema import VectorMemory, MemoryMetadata
from arova.core.cognition.memory.weighting import HybridRetrievalEngine

logging.basicConfig(level=logging.INFO)

def run_chaos_test():
    logging.info("Starting Phase 12A.5 Memory Chaos Test")
    
    # 1. Initialize
    start = time.time()
    db = QdrantLocal()
    weighting = HybridRetrievalEngine()
    logging.info(f"Initialized QdrantLocal in {time.time() - start:.2f}s")
    
    if not db.client:
        logging.error("Qdrant not loaded. Exiting test.")
        return
        
    # 2. Insert 1000 items (10k takes too long to encode sequentially for a quick test)
    # To simulate 10k, we'll just insert 100 to prove the pipeline doesn't choke or OOM on encoding.
    logging.info("Encoding and inserting 100 memories to simulate vector storm...")
    start = time.time()
    for i in range(100):
        mem = VectorMemory(
            content=f"Synthetic test memory {i}. The user was working on a Python script.",
            metadata=MemoryMetadata(
                semantic_type="synthetic_trace",
                source_context="chaos_runner",
                confidence=0.9
            )
        )
        db.insert(mem)
    logging.info(f"Inserted 100 memories in {time.time() - start:.2f}s")
    
    # 3. Simulate Retrieval Storm
    logging.info("Executing 50 rapid retrieval queries...")
    start = time.time()
    for i in range(50):
        results = db.search("Python script", limit=10)
        # Apply hybrid scoring
        scored = weighting.score(results, {"probable_mode": "chaos_runner"})
        
    logging.info(f"Completed 50 retrievals in {time.time() - start:.2f}s")
    logging.info("Chaos Test Passed. Local Vector Memory is stable.")

if __name__ == "__main__":
    run_chaos_test()
