from sentence_transformers import SentenceTransformer, util
import torch

# Initialize the Sentence-BERT model
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

def get_similar_sentences(input_statement, statements_set):
    # Encode sentences to get their embeddings
    input_embedding = model.encode(input_statement, convert_to_tensor=True)
    statements_embeddings = model.encode(statements_set, convert_to_tensor=True)

    # Compute similarity scores
    similarity_scores = util.pytorch_cos_sim(input_embedding, statements_embeddings)[0]

    # Convert similarity scores from tensor to list
    similarity_scores = similarity_scores.tolist()

    return similarity_scores