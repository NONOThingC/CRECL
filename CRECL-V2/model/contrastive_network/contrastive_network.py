# -- coding: utf-8 --
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from ..base_model import base_model
from transformers import BertModel, BertConfig

LARGE_NUM = 1e9


class ContrastiveNetwork(base_model):

    def __init__(self, config, hidden_size):

        super(ContrastiveNetwork, self).__init__()
        self.config = config
        # self.encoder = encoder
        # self.dropout_layer = dropout_layer
        self.hidden_size = hidden_size
        # self.dim_trans = nn.Linear(config.encoder_output_size, hidden_size)
        self.output_size = config.encoder_output_size  # for classification number
        self.projector = nn.Linear(hidden_size, self.output_size // 10)
        # self.emb_trans = nn.Linear(hidden_size, hidden_size)
        self.gelu = nn.GELU()
        self.projector1 = nn.Linear(self.output_size // 10, self.output_size // 10, bias=False)
        self.temperature = config.temperature
        self.layer_normalization = nn.LayerNorm([config.output_size])
        # self.dropout=nn.Dropout(config.drop_p)

    def forward(self, left, right, comparison=None, memory_network=None, mem_for_batch=None, FUN_CODE=1):
        if FUN_CODE == 2:
            mid_hidden = self.encoder(enc_inp)
            if mid_hidden.shape[1] != self.hidden_size:
                mid_hidden = self.dim_trans(mid_hidden)
            proj_inp = self.emb_trans(proj_inp)
            hidden = self.projector1(
                self.layer_normalization(self.gelu(self.projector(torch.cat([mid_hidden, proj_inp], dim=0)))))

            hidden = F.normalize(hidden, dim=-1, p=2)
            # hidden = torch.linalg.norm(hidden, dim=-1)
            hidden1, hidden2 = torch.split(hidden, [len(enc_inp), len(proj_inp)], dim=0)
            logits_aa = torch.matmul(hidden1, torch.transpose(hidden2, -1, -2)) / self.temperature  # B1*B2
            logits_aa = logits_aa + (comparison == 0).float() * (-LARGE_NUM)  # mask#B1 * B2
            return logits_aa
        elif FUN_CODE == 0:  # mem
            self.encoder.eval()
            self.dropout_layer.eval()

            with torch.no_grad():
                right = self.dropout_layer(self.encoder(proj_inp))[1]
            right.detach_()
            self.encoder.train()
            self.dropout_layer.train()

            left = self.dropout_layer(self.encoder(enc_inp))[1]

            # mem_for_batch = mem_for_batch.expand(len(left), -1, -1)

            hidden = memory_network(torch.cat([left, right], dim=0), mem_for_batch)
            hidden = self.projector1(self.layer_normalization(self.gelu(self.projector(hidden))))
            hidden = F.normalize(hidden, dim=-1, p=2)
            # hidden = torch.linalg.norm(hidden, dim=-1)
            hidden1, hidden2 = torch.split(hidden, [len(left), len(right)], dim=0)
            logits_aa = torch.matmul(hidden1, torch.transpose(hidden2, -1, -2)) / self.temperature  # B*K
            logits_aa = logits_aa + (comparison == 0).float() * (-LARGE_NUM)  # mask#B1 * B2
            return logits_aa
        elif FUN_CODE == 1:
            self.encoder.eval()
            self.dropout_layer.eval()

            with torch.no_grad():
                right = self.dropout_layer(self.encoder(proj_inp))[1]
            right.detach_()
            self.encoder.train()
            self.dropout_layer.train()

            left = self.dropout_layer(self.encoder(enc_inp))[1]

            hidden = torch.cat([left, right], dim=0)
            hidden = self.projector1(self.layer_normalization(self.gelu(self.projector(hidden))))
            hidden = F.normalize(hidden, dim=-1, p=2)
            # hidden = torch.linalg.norm(hidden, dim=-1)
            hidden1, hidden2 = torch.split(hidden, [len(left), len(right)], dim=0)
            logits_aa = torch.matmul(hidden1, torch.transpose(hidden2, -1, -2)) / self.temperature  # B*K
            logits_aa = logits_aa + (comparison == 0).float() * (-LARGE_NUM)  # mask#B1 * B2
            return logits_aa
        elif FUN_CODE == 3:  # mem,fix prototype
            left = self.dropout_layer(self.encoder(enc_inp))[1]
            hidden = memory_network(torch.cat([left, proj_inp], dim=0), mem_for_batch)
            hidden = self.projector1(self.layer_normalization(self.gelu(self.projector(hidden))))
            hidden = F.normalize(hidden, dim=-1, p=2)
            hidden1, hidden2 = torch.split(hidden, [len(left), len(proj_inp)], dim=0)
            logits_aa = torch.matmul(hidden1, torch.transpose(hidden2, -1, -2)) / self.temperature  # B*K
            logits_aa = logits_aa + (comparison == 0).float() * (-LARGE_NUM)  # mask#B1 * B2
            return logits_aa
        elif FUN_CODE == 4:  # no mem, fix prototype
            m, n = len(left), len(right)
            hidden = torch.cat([left, right], dim=0)
            hidden = self.projector1(self.gelu(self.projector(hidden)))  # sent,proto
            hidden = F.normalize(hidden, dim=-1, p=2)
            hidden1, hidden2 = torch.split(hidden, [m, n], dim=0)
            logits_aa = torch.matmul(hidden1 / self.temperature, torch.transpose(hidden2, -1, -2))  # B*K
            return logits_aa
        elif FUN_CODE == 5:  # mem,fix sentence,change prototype,left is sentence,enc_inp is prototype need to be calculated
            with torch.no_grad():
                left = self.dropout_layer(self.encoder(enc_inp))[1]
            proj_inp = torch.mean(self.dropout_layer(self.encoder(enc_inp))[1], dim=1)
            hidden = memory_network(torch.cat([left, proj_inp], dim=0), mem_for_batch)
            hidden = self.projector1(self.layer_normalization(self.gelu(self.projector(hidden))))
            hidden = F.normalize(hidden, dim=-1, p=2)
            hidden1, hidden2 = torch.split(hidden, [len(left), len(proj_inp)], dim=0)
            logits_aa = torch.matmul(hidden1, torch.transpose(hidden2, -1, -2)) / self.temperature  # B*K
            logits_aa = logits_aa + (comparison == 0).float() * (-LARGE_NUM)  # mask#B1 * B2
            return logits_aa
        elif FUN_CODE == 6:  # no mem,fix sentence,change prototype,left is sentence,enc_inp is prototype need to be calculated
            # print(f"enc:{enc_inp.shape},pro_inp:{proj_inp.shape}")
            with torch.no_grad():
                left = self.dropout_layer(self.encoder(enc_inp))[1]
            tmp = proj_inp.shape[0]
            proj_inp = proj_inp.view(-1, proj_inp.shape[-1])
            proj_inp = self.dropout_layer(self.encoder(proj_inp))[1]
            proj_inp = proj_inp.view(tmp, -1, proj_inp.shape[-1])
            right = torch.mean(proj_inp, dim=1)
            # print(f"left {left.shape},right {right.shape}")
            hidden = torch.cat([left, right], dim=0)
            hidden = self.projector1(self.layer_normalization(self.gelu(self.projector(hidden))))
            hidden = F.normalize(hidden, dim=-1, p=2)
            # hidden = torch.linalg.norm(hidden, dim=-1)
            hidden1, hidden2 = torch.split(hidden, [len(left), len(right)], dim=0)
            logits_aa = torch.matmul(hidden1, torch.transpose(hidden2, -1, -2)) / self.temperature  # B*K
            logits_aa = logits_aa + (comparison == 0).float() * (-LARGE_NUM)  # mask#B1 * B2
            return logits_aa
        elif FUN_CODE == 7:  # bak
            # no mem, fix prototype
            m, n = len(left), len(right)
            hidden = torch.cat([left, right], dim=0)
            hidden = self.projector1(self.layer_normalization(self.gelu(self.projector(hidden))))  # sent,proto

            _, t2 = torch.split(hidden, [m, n], dim=0)
            tmp_h = len(t2)
            if tmp_h > self.config.rel_per_task:
                beta = torch.norm(t2[:-self.config.rel_per_task], p=2, dim=-1).mean() / torch.norm(
                    t2[-self.config.rel_per_task:], p=2, dim=-1).mean()

            hidden = F.normalize(hidden, dim=-1, p=2)

            hidden1, hidden2 = torch.split(hidden, [m, n], dim=0)

            if tmp_h > self.config.rel_per_task:
                tmp = torch.cat([torch.ones(tmp_h - self.config.rel_per_task, device=self.config.device),
                                 beta * torch.ones(self.config.rel_per_task, device=self.config.device)],
                                dim=0).view(-1, 1).repeat(1, hidden2.shape[1])
                hidden2 = hidden2 * tmp
            logits_aa = torch.matmul(hidden1 / self.temperature, torch.transpose(hidden2, -1, -2))  # B*K
            return logits_aa

    def forward_no_mem(self, enc_inp, proj_inp, comparison):

        self.encoder.eval()
        self.dropout_layer.eval()

        with torch.no_grad():
            right = self.dropout_layer(self.encoder(proj_inp))[1]
        right.detach_()
        self.encoder.train()
        self.dropout_layer.train()

        left = self.dropout_layer(self.encoder(enc_inp))[1]

        hidden = torch.cat([left, right], dim=0)
        hidden = self.projector1(self.gelu(self.projector(hidden)))
        hidden1, hidden2 = torch.split(hidden, [len(left), len(right)], dim=0)

        hidden = F.normalize(hidden, dim=-1, p=2)
        # hidden = torch.linalg.norm(hidden, dim=-1)

        logits_aa = torch.matmul(hidden1, torch.transpose(hidden2, -1, -2)) / self.temperature  # B*K
        logits_aa = logits_aa + (comparison == 0).float() * (-LARGE_NUM)  # mask#B1 * B2
        return logits_aa

    def align_norms(self):
        # Fetch old and new layers
        new_layer = self.projector1
        old_layers = self.projector

        # Get weight of layers
        new_weight = new_layer.weight.cpu().detach().numpy()
        old_weight = old_layers.weight.cpu().detach().numpy()
        # for i in range(step_b):
        #     old_weight = np.concatenate([old_layers[i].weight.cpu().detach().numpy() for i in range(step_b)])
        print("old_weight's shape is: ", old_weight.shape)
        print("new_weight's shape is: ", new_weight.shape)

        # Calculate the norm
        Norm_of_new = np.linalg.norm(new_weight, axis=1)
        Norm_of_old = np.linalg.norm(old_weight, axis=1)

        # Calculate the Gamma
        gamma = np.mean(Norm_of_old) / np.mean(Norm_of_new)
        print("Gamma = ", gamma)
        # Update new layer's weight
        updated_new_weight = torch.Tensor(gamma * new_weight).cuda()
        self.projector1.weight = torch.nn.Parameter(updated_new_weight)
