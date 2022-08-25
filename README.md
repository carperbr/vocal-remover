# vocal-remover

This is a deep-learning-based tool to extract instrumental track from your songs.

Currently testing out a new architecture. The current architecture can be found in frame_transformer.py in the root directory, everything but the rotary positional embeddings are found in that file. The nueral network consists of a residual u-net where the encoders are defined as frame_transformer_encoder(frame_encoder(x)), and the decoders are defined as frame_transformer_decoder(frame_decoder(x, skip), skip). Frame encoders and frame decoders no longer use convolutions; instead, they utilize a position-wise linear residual block via the MultichannelLinear module. MultichannelLinear has both a per-channel position-wise weight matrix as well as an optional depth-wise weight matrix with the depth-wise transformation carried out first. Since these now use fully connected layers, both the frame encoder and frame decoder feature dropout on the residual. Each u-net encoder is defined as frame_transformer_encoder(frame_encoder(x)), and each u-net decoder is defined as frame_transformer_decoder(frame_decoder(x, skip), skip). Frame decoders utilize the u-net skip connection for memory. The frame transformer modules utilize the primer architecture with some changes for multiple channels. Both use multichannel multihead attention which adds a channel dimension to multihead attention; for projections, multichannel multihead attention uses position-wise-only multichannel linear layers followed by a 2d convolution with kernel size of 1xN; this is equivalent to the primer architectures use of convolutions extended into 2d and is the only place where convolutions are used in this neural network (aside from the depth-wise matrix multiplications since those are technically 1x1 convolutions). So far it is performing around the same while shaving off 2 hours from each epoch (4.5 hours to 2.5).

This fork also makes use of a dataset I refer to as voxaug. This dataset randomly selects from a library of instrumental music and a library of vocal tracks and mixes them together for the neural network to train on. This has the benefit of inflating data exponentially as well as ensuring data is perfect for the removal process. To an extent you could view this as self-supervised learning in that its learning to remove a mask of vocals. My instrumental dataset consists of 30.88 days worth of music while my vocal stem library consists of 1416 full song vocal tracks.

## References
- [1] Jansson et al., "Singing Voice Separation with Deep U-Net Convolutional Networks", https://ismir2017.smcnus.org/wp-content/uploads/2017/10/171_Paper.pdf
- [2] Takahashi et al., "Multi-scale Multi-band DenseNets for Audio Source Separation", https://arxiv.org/pdf/1706.09588.pdf
- [3] Takahashi et al., "MMDENSELSTM: AN EFFICIENT COMBINATION OF CONVOLUTIONAL AND RECURRENT NEURAL NETWORKS FOR AUDIO SOURCE SEPARATION", https://arxiv.org/pdf/1805.02410.pdf
- [4] Liutkus et al., "The 2016 Signal Separation Evaluation Campaign", Latent Variable Analysis and Signal Separation - 12th International Conference
- [5] Vaswani et al., "Attention Is All You Need", https://arxiv.org/pdf/1706.03762.pdf
- [6] So et al., "Primer: Searching for Efficient Transformers for Language Modeling", https://arxiv.org/pdf/2109.08668v2.pdf
- [7] Su et al., "RoFormer: Enhanced Transformer with Rotary Position Embedding", https://arxiv.org/abs/2104.09864
- [8] Asiedu et all., "Decoder Denoising Pretraining for Semantic Segmentation", https://arxiv.org/abs/2205.11423
