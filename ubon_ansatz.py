# -*- coding: utf-8 -*-
"""UBoN_ansatz.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1PtkWina8vuSAIQ3G6qwaldjoaJD37KFv
"""

from jax.scipy.special import logsumexp
from dataclasses import field # para asegurar datos hashable
import jax.numpy as jnp
import flax.linen as nn
import jax

class NodeMLP(nn.Module):
    '''
    Módulo de Flax que define la MLP a nivel nodal.
    '''
    @nn.compact
    def __call__(self, x):
        x = nn.Dense(128)(x)
        x = nn.relu(x)
        x = nn.Dense(64)(x)
        x = nn.relu(x)
        x = nn.Dense(32)(x)
        x = nn.relu(x)
        x = nn.Dense(1)(x)
        return x


class node_level_MLP(nn.Module):
    '''
    Módulo de Flax que define la MLP a nivel de nodo.

    Args: N (int): Número de nodos en el grafo.
          augmentation (jnp.ndarray): Matriz de de codificación EASE.
    '''
    N: int
    augmentation: jnp.ndarray = field(default=None, repr=False, hash=False, compare=False, metadata={"flax": {"static": True}})


    @nn.compact
    def __call__(self, node_features):
        input = jnp.expand_dims(node_features, axis=-1)
        num_batch = input.shape[0]
        augmentation = jnp.broadcast_to(self.augmentation, (num_batch, self.N, self.N))
        augmented_input = jnp.concatenate((input, augmentation), axis=-1)

        #aplicamos la capa de la MLP a todas las batch, con los mismos parámetros para cada batch
        batched_mlp = nn.vmap(
            NodeMLP,
            in_axes=0,
            out_axes=0,
            variable_axes={'params': None},
            split_rngs={'params': False}
        )()

        return batched_mlp(augmented_input)

class graph_level_MLP(nn.Module):
  '''
  Módulo de Flax que define la MLP a nivel de grafo.

  Args: N (int): Número de nodos en el grafo.
        augmentation (jnp.ndarray): Matriz de de codificación EASE.
  '''
  N: int
  augmentation: jnp.ndarray = field(default=None, repr=False, hash=False, compare=False, metadata={"flax": {"static": True}})

  @nn.compact
  def __call__(self, node_features):
    print(node_features.shape)


    primer_MLP = node_level_MLP(self.N, self.augmentation)(node_features)
    x = jnp.mean(primer_MLP, axis=1)
    x = nn.Dense(64)(x)
    x = nn.relu(x)
    x = nn.Dense(1)(x)     # (batch, 1)
    return x.reshape((-1,))  # (batch,) garantizado

class sym_UBoN(nn.Module):
    '''
    Módulo de Flax que introduce simetría de inversión.

    Args: trivial (bool): Si es True, se construyen funciones de la irrep trivial. False lo contario.
          N (int): Número de nodos en el grafo.
          augmentation (jnp.ndarray): Matriz de de codificación EASE.
          dtype (jnp.dtype): Tipo de datos a usar.
    '''
    trivial: bool
    N: int
    augmentation: jnp.ndarray = field(default=None, repr=False, hash=False, compare=False, metadata={"flax": {"static": True}})
    dtype: jnp.dtype = jnp.float32

    @nn.compact
    def __call__(self, node_features):
        model = graph_level_MLP(
          N=self.N,
          augmentation = self.augmentation,
      )
        output_x = model(node_features)
        output_inv_x = model(-1*node_features)

        if self.trivial:
            return logsumexp(jnp.array([output_x, output_inv_x]), axis = 0)
        else:
            weights = jnp.asarray([1., -1.])  # Ahora tiene forma (2, 1)
            weights = jnp.expand_dims(weights, axis=1)
            log_psi =  logsumexp(jnp.stack([output_x+0.j, output_inv_x+0.j]), b=weights , axis=0)
            return log_psi