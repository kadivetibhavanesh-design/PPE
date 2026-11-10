
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix
import numpy as np

# PPE detection classes
classes = [
    "Person",
    "Helmet",
    "Safety Vest",
    "Gloves",
    "Safety Goggles",
    "Safety Shoes"
]

# Illustrative sample data only
# Replace with actual model predictions before using in your paper
y_true = (
    [0]*100 + [1]*100 + [2]*100 +
    [3]*100 + [4]*100 + [5]*100
)

y_pred = (
    [0]*90 + [1]*5 + [2]*3 + [3]*2 +
    [1]*88 + [0]*5 + [2]*4 + [4]*3 +
    [2]*91 + [0]*4 + [1]*3 + [3]*2 +
    [3]*85 + [1]*5 + [2]*5 + [4]*5 +
    [4]*89 + [1]*5 + [2]*3 + [5]*3 +
    [5]*90 + [1]*4 + [2]*3 + [4]*3
)

# Generate confusion matrix
cm = confusion_matrix(
    y_true,
    y_pred,
    labels=range(len(classes))
)

# Calculate accuracy for this illustrative example
accuracy = np.trace(cm) / np.sum(cm) * 100

# Create figure
plt.figure(figsize=(11, 8))

sns.heatmap(
    cm,
    annot=True,
    fmt="d",
    cmap="Blues",
    xticklabels=classes,
    yticklabels=classes,
    linewidths=0.5,
    linecolor="white",
    cbar=True,
    annot_kws={"size": 11}
)

# Titles and labels
plt.title(
    "Confusion Matrix for PPE Detection",
    fontsize=16,
    fontweight="bold",
    pad=20
)

plt.xlabel("Predicted Class", fontsize=13, fontweight="bold")
plt.ylabel("Actual Class", fontsize=13, fontweight="bold")

plt.xticks(rotation=35, ha="right", fontsize=10)
plt.yticks(rotation=0, fontsize=10)

# Accuracy annotation
plt.figtext(
    0.5, 0.01,
    f"Illustrative Sample Accuracy: {accuracy:.2f}%",
    ha="center",
    fontsize=11
)

plt.tight_layout(rect=[0, 0.04, 1, 1])

# Save high-resolution image
plt.savefig(
    "PPE_Confusion_Matrix.png",
    dpi=600,
    bbox_inches="tight"
)

plt.show()

print("Confusion Matrix:")
print(cm)
print(f"Illustrative Accuracy: {accuracy:.2f}%")
print("Image saved as PPE_Confusion_Matrix.png")
