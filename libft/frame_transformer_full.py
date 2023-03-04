import torch
from torch import nn
from libft.positional_embedding import PositionalEmbedding
from libft.multihead_channel_attention import MultiheadChannelAttention
from libft.multichannel_multihead_attention import MultichannelMultiheadAttention
from libft.multichannel_layernorm import MultichannelLayerNorm
from libft.multichannel_linear import MultichannelLinear

class FrameTransformer(nn.Module):
    def __init__(self, in_channels=2, out_channels=2, channels=2, dropout=0.1, n_fft=2048, num_heads=4, expansion=4, transformer_channels=[4,8,12,32,64,128,512]):
        super(FrameTransformer, self).__init__(),
        
        self.max_bin = n_fft // 2
        self.output_bin = n_fft // 2 + 1

        self.positional_embedding = PositionalEmbedding(in_channels, self.max_bin)

        self.enc1 = FrameEncoder(in_channels, channels, self.max_bin, downsample=False)
        self.enc1_transformer = FrameTransformerEncoder(channels, self.max_bin, dropout=dropout, expansion=expansion, num_heads=num_heads)

        self.enc2 = FrameEncoder(channels, channels * 2, self.max_bin)
        self.enc2_transformer = FrameTransformerEncoder(channels * 2, self.max_bin // 2, dropout=dropout, expansion=expansion, num_heads=num_heads)

        self.enc3 = FrameEncoder(channels * 2, channels * 4, self.max_bin // 2)
        self.enc3_transformer = FrameTransformerEncoder(channels * 4, self.max_bin // 4, dropout=dropout, expansion=expansion, num_heads=num_heads)

        self.enc4 = FrameEncoder(channels * 4, channels * 8, self.max_bin // 4)
        self.enc4_transformer = FrameTransformerEncoder(channels * 8, self.max_bin // 8, dropout=dropout, expansion=expansion, num_heads=num_heads)

        self.enc5 = FrameEncoder(channels * 8, channels * 16, self.max_bin // 8)
        self.enc5_transformer = FrameTransformerEncoder(channels * 16, self.max_bin // 16, dropout=dropout, expansion=expansion, num_heads=num_heads)

        self.enc6 = FrameEncoder(channels * 16, channels * 32, self.max_bin // 16)
        self.enc6_transformer = FrameTransformerEncoder(channels * 32, self.max_bin // 32, dropout=dropout, expansion=expansion, num_heads=num_heads)
        
        self.bridge = nn.Sequential(*[FrameTransformerBridge(channels * 32, self.max_bin // 32, dropout=dropout, expansion=expansion, num_heads=num_heads) for _ in range(11)])
        
        self.dec5 = FrameDecoder(channels * 32, channels * 16, self.max_bin // 16)
        self.dec5_transformer = FrameTransformerDecoder(channels * 16, self.max_bin // 16, dropout=dropout, expansion=expansion, num_heads=num_heads)
        
        self.dec4 = FrameDecoder(channels * 16, channels * 8, self.max_bin // 8)
        self.dec4_transformer = FrameTransformerDecoder(channels * 8, self.max_bin // 8, dropout=dropout, expansion=expansion, num_heads=num_heads)
        
        self.dec3 = FrameDecoder(channels * 8, channels * 4, self.max_bin // 4)
        self.dec3_transformer = FrameTransformerDecoder(channels * 4, self.max_bin // 4, dropout=dropout, expansion=expansion, num_heads=num_heads)
        
        self.dec2 = FrameDecoder(channels * 4, channels * 2, self.max_bin // 2)
        self.dec2_transformer = FrameTransformerDecoder(channels * 2, self.max_bin // 2, dropout=dropout, expansion=expansion, num_heads=num_heads)
        
        self.dec1 = FrameDecoder(channels * 2, channels * 1, self.max_bin)
        self.dec1_transformer = FrameTransformerDecoder(channels * 1, self.max_bin // 1, dropout=dropout, expansion=expansion, num_heads=num_heads, groups=1)

        self.out = nn.Conv2d(channels, out_channels, kernel_size=1, padding=0, groups=1)

    def __call__(self, x):
        x = x + self.positional_embedding(x)

        e1 = self.enc1(x)
        e1, e1qk = self.enc1_transformer(e1)
        e2 = self.enc2(e1)
        e2, e2qk = self.enc2_transformer(e2)
        e3 = self.enc3(e2)
        e3, e3qk = self.enc3_transformer(e3)
        e4 = self.enc4(e3)
        e4, e4qk = self.enc4_transformer(e4)
        e5 = self.enc5(e4)
        e5, e5qk = self.enc5_transformer(e5)
        e6 = self.enc6(e5)
        e6, _ = self.enc6_transformer(e6)

        prev_qk = None
        for module in self.bridge:
            e6, prev_qk = module(e6, prev_qk)

        d5 = self.dec5(e6, e5)
        d5 = self.dec5_transformer(d5, skip=e5, skip_qk=e5qk)
        
        d4 = self.dec4(d5, e4)
        d4 = self.dec4_transformer(d4, skip=e4, skip_qk=e4qk)
        
        d3 = self.dec3(d4, e3)
        d3 = self.dec3_transformer(d3, skip=e3, skip_qk=e3qk)
        
        d2 = self.dec2(d3, e2)
        d2 = self.dec2_transformer(d2, skip=e2, skip_qk=e2qk)
        
        d1 = self.dec1(d2, e1)
        d1 = self.dec1_transformer(d1, skip=e1, skip_qk=e1qk)

        out = self.out(d1)

        return out
        
class FrameTransformerEncoder(nn.Module):
    def __init__(self, channels, features, dropout=0.1, expansion=4, num_heads=8, groups=2):
        super(FrameTransformerEncoder, self).__init__()

        self.activate = SquaredReLU()
        self.dropout = nn.Dropout(dropout)

        self.norm0 = MultichannelLayerNorm(channels, features)
        self.attn0 = MultiheadChannelAttention(channels, num_heads)

        self.norm1 = MultichannelLayerNorm(channels, features)
        self.attn = MultichannelMultiheadAttention(channels, num_heads, features, depthwise=True)

        self.norm2 = MultichannelLayerNorm(channels, features)
        self.conv1 = MultichannelLinear(channels, channels, features, features * expansion, depthwise=True)
        self.conv2 = MultichannelLinear(channels, channels, features * expansion, features)

    def __call__(self, x):
        z = self.attn0(self.norm0(x))
        h = x + self.dropout(z)

        z, prev_qk = self.attn(self.norm1(h))
        h = h + self.dropout(z)

        z = self.conv2(self.activate(self.conv1(self.norm2(h))))
        h = h + self.dropout(z)

        return h, prev_qk
        
class FrameTransformerBridge(nn.Module):
    def __init__(self, channels, features, dropout=0.1, expansion=4, num_heads=8, groups=2):
        super(FrameTransformerBridge, self).__init__()

        self.activate = SquaredReLU()
        self.dropout = nn.Dropout(dropout)

        self.norm0 = MultichannelLayerNorm(channels, features)
        self.attn0 = MultiheadChannelAttention(channels, num_heads)

        self.norm1 = MultichannelLayerNorm(channels, features)
        self.attn = MultichannelMultiheadAttention(channels, num_heads, features, depthwise=True)

        self.norm2 = MultichannelLayerNorm(channels, features)
        self.conv1 = MultichannelLinear(channels, channels, features, features * expansion, depthwise=True)
        self.conv2 = MultichannelLinear(channels, channels, features * expansion, features)

    def __call__(self, x, prev_qk=None):
        z = self.attn0(self.norm0(x))
        h = x + self.dropout(z)

        z, prev_qk = self.attn(self.norm1(h), prev_qk=prev_qk)
        h = h + self.dropout(z)

        z = self.conv2(self.activate(self.conv1(self.norm2(h))))
        h = h + self.dropout(z)

        return h, prev_qk
        
class FrameTransformerDecoder(nn.Module):
    def __init__(self, channels, features, dropout=0.1, expansion=4, num_heads=8, groups=2):
        super(FrameTransformerDecoder, self).__init__()

        self.activate = SquaredReLU()
        self.dropout = nn.Dropout(dropout)

        self.norm0a = MultichannelLayerNorm(channels, features)
        self.attn0a = MultiheadChannelAttention(channels, num_heads)

        self.norm0b = MultichannelLayerNorm(channels, features)
        self.attn0b = MultiheadChannelAttention(channels, num_heads)

        self.norm1 = MultichannelLayerNorm(channels, features)
        self.attn1 = MultichannelMultiheadAttention(channels, num_heads, features, depthwise=True)

        self.norm2 = MultichannelLayerNorm(channels, features)
        self.attn2 = MultichannelMultiheadAttention(channels, num_heads, features, depthwise=True)

        self.norm3 = MultichannelLayerNorm(channels, features)
        self.conv1 = MultichannelLinear(channels, channels, features, features * expansion, depthwise=True)
        self.conv2 = MultichannelLinear(channels, channels, features * expansion, features)
        
    def __call__(self, x, skip, skip_qk=None):
        z = self.attn0a(self.norm0a(x))
        h = x + self.dropout(z)

        z, _ = self.attn1(self.norm1(h), prev_qk=skip_qk)
        h = h + self.dropout(z)

        z = self.attn0b(self.norm0b(skip))
        skip = skip + self.dropout(z)

        z, _ = self.attn2(self.norm2(h), mem=skip, prev_qk=skip_qk)
        h = h + self.dropout(z)

        z = self.conv2(self.activate(self.conv1(self.norm3(h))))
        h = h + self.dropout(z)

        return h

class SquaredReLU(nn.Module):
    def __call__(self, x):
        return torch.relu(x) ** 2

class ResBlock(nn.Module):
    def __init__(self, in_channels, out_channels, features, downsample=False, upsample=False):
        super(ResBlock, self).__init__()

        self.downsample = downsample
        self.activate = SquaredReLU()
        self.norm = MultichannelLayerNorm(in_channels, features)
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, stride=(2,1) if downsample else 1)
        self.conv2 = nn.Conv2d(out_channels , out_channels, kernel_size=3, padding=1)
        self.identity = nn.Conv2d(in_channels, out_channels, kernel_size=1, padding=0, stride=(2,1) if downsample else 1) if (not downsample and in_channels != out_channels) or downsample else nn.Identity()

    def __call__(self, x):
        h = self.conv2(self.activate(self.conv1(self.norm(x))))
        x = self.identity(x) + h

        return x

class FrameEncoder(nn.Module):
    def __init__(self, in_channels, out_channels, features, downsample=True):
        super(FrameEncoder, self).__init__()

        self.downsample = downsample
        self.body = ResBlock(in_channels * 2 if downsample else in_channels, in_channels * 2 if downsample else out_channels, features, downsample=downsample)

    def __call__(self, x):
        if self.downsample:
            x = torch.cat((x[:, :, :, :x.shape[3] // 2], x[:, :, :, x.shape[3] // 2:]), dim=1)

        x = self.body(x)

        return x

class FrameDecoder(nn.Module):
    def __init__(self, in_channels, out_channels, features):
        super(FrameDecoder, self).__init__()

        self.upsample = nn.ConvTranspose2d(out_channels * 2, out_channels * 2, kernel_size=(4,3), padding=1, stride=(2,1))
        self.body = ResBlock(out_channels * 4, out_channels * 2, features)

    def __call__(self, x, skip):
        x = self.upsample(x)
        x = torch.cat((x[:, :(x.shape[1] // 2), :, :], skip[:, :, :, :skip.shape[3] // 2], x[:, (x.shape[1] // 2):], skip[:, :, :, skip.shape[3] // 2:]), dim=1)
        x = self.body(x)
        x = torch.cat((x[:, :(x.shape[1] // 2), :, :], x[:, (x.shape[1] // 2):]), dim=3)

        return x