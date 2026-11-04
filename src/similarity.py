
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer("all-MiniLM-L6-v2")

sentences = [
    "How can I apply for leave?",
    "What is the process for requesting time off?",
    "The weather is very hot today."
]

embeddings = model.encode(sentences)

similarity_matrix = cosine_similarity(embeddings)

for i in range(len(sentences)):
    for j in range(i + 1, len(sentences)):
        print(
            f"\nSimilarity between:\n"
            f"{sentences[i]}\n"
            f"{sentences[j]}\n"
            f"Score: {similarity_matrix[i][j]:.4f}"
        )
