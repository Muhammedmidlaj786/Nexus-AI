
from sentence_transformers import SentenceTransformer

# Load a pretrained embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

sentences = [
    "How can I apply for leave?",
    "What is the process for requesting time off?",
    "The weather is very hot today."
]

# Convert text into numerical vectors
embeddings = model.encode(sentences)

print("Shape:", embeddings.shape)

for sentence, embedding in zip(sentences, embeddings):
    print("\nSentence:", sentence)
    print("Embedding:", embedding[:5])
