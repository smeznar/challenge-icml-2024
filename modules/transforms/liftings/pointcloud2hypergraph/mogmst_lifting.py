import numpy as np
import torch
import torch_geometric
from networkx import from_numpy_array, minimum_spanning_tree
from sklearn.metrics import pairwise_distances, silhouette_score
from sklearn.mixture import GaussianMixture

from modules.transforms.liftings.pointcloud2hypergraph.base import (
    PointCloud2HypergraphLifting,
)


class MoGMSTLifting(PointCloud2HypergraphLifting):
    def __init__(
        self, min_components=2, max_components=10, random_state=None, **kwargs
    ):
        super().__init__(**kwargs)
        self.min_components = min_components
        self.max_components = max_components
        self.random_state = random_state

    def lift_topology(self, data: torch_geometric.data.Data) -> dict:
        # Find a mix of Gaussians
        labels, num_components, means = self.find_mog(data.pos.numpy())

        # Create MST
        distance_matrix = pairwise_distances(means)
        original_graph = from_numpy_array(distance_matrix)
        mst = minimum_spanning_tree(original_graph)

        # create hipergraph
        number_of_points = data.x.shape[0]
        incidence = torch.zeros((number_of_points, 2 * num_components))
        incidence[torch.range(0, number_of_points), torch.tensor(labels)] = torch.ones(
            number_of_points
        )
        for i, j in mst.edges():
            mask_i = labels == i
            mask_j = labels == j
            incidence[mask_i, torch.ones(mask_i.shape[0]) + num_components + j] = 1

        return {
            "incidence_hyperedges": incidence,
            "num_hyperedges": 2 * num_components,
            "x_0": data.x,
        }

    def find_mog(self, data) -> tuple[np.ndarray, int, np.ndarray]:
        best_silhouette = -1
        best_labels = None
        best_num_components = 0
        means = None
        for i in range(self.min_components, self.max_components):
            gm = GaussianMixture(n_components=i, random_state=self.random_state)
            labels = gm.fit_predict(data)
            sc = silhouette_score(data, labels)
            if sc > best_silhouette:
                best_silhouette = sc
                best_labels = labels
                best_num_components = i
                means = gm.means_
        return best_labels, best_num_components, means