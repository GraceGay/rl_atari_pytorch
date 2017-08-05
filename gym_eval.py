from __future__ import division
import os
os.environ["OMP_NUM_THREADS"] = "1"
import argparse
import torch
from environment import atari_env
from utils import read_config, setup_logger
from model import A3Clstm
from player_util import Agent, player_act, player_start
from torch.autograd import Variable
import gym
import logging

parser = argparse.ArgumentParser(description='A3C_EVAL')
parser.add_argument(
    '--env',
    default='Pong-v0',
    metavar='ENV',
    help='environment to train on (default: Pong-v0)')
parser.add_argument(
    '--env-config',
    default='config.json',
    metavar='EC',
    help='environment to crop and resize info (default: config.json)')
parser.add_argument(
    '--num-episodes',
    type=int,
    default=100,
    metavar='NE',
    help='how many episodes in evaluation (default: 100)')
parser.add_argument(
    '--load-model-dir',
    default='checkpoints/',
    metavar='LMD',
    help='folder to load trained models from')
parser.add_argument(
    '--log-dir',
    default='logs/',
    metavar='LG',
    help='folder to save logs')
parser.add_argument(
    '--render',
    default=True,
    metavar='R',
    help='Watch game as it being played')
parser.add_argument(
    '--render-freq',
    type=int,
    default=1,
    metavar='RF',
    help='Frequency to watch rendered game play')
parser.add_argument(
    '--max-episode-length',
    type=int,
    default=100000,
    metavar='M',
    help='maximum length of an episode (default: 100000)')
args = parser.parse_args()

setup_json = read_config(args.env_config)
env_conf = setup_json["Default"]
for i in setup_json.keys():
    if i in args.env:
        env_conf = setup_json[i]
torch.set_default_tensor_type('torch.FloatTensor')

saved_state_path = os.path.join(args.load_model_dir, args.env + '.model')
saved_state = torch.load(saved_state_path, map_location=lambda storage, loc: storage)
print('Loaded trained model from: {}'.format(saved_state_path))

log = {}
setup_logger('{}_mon_log'.format(args.env), r'{0}{1}_mon_log'.format(
    args.log_dir, args.env))
log['{}_mon_log'.format(args.env)] = logging.getLogger(
    '{}_mon_log'.format(args.env))

env = atari_env("{}".format(args.env), env_conf)
model = A3Clstm(env.observation_space.shape[0], env.action_space)

num_tests = 0
reward_total_sum = 0
player = Agent(model, env, args, state=None)
player.env = gym.wrappers.Monitor(player.env, "{}_monitor".format(args.env), force=True)
player.model.eval()
for i_episode in range(args.num_episodes):
    state = player.env.reset()
    player.state = torch.from_numpy(state).float()
    player.eps_len = 0
    reward_sum = 0
    while True:
        if args.render:
            if i_episode % args.render_freq == 0:
                player.env.render()
        if player.done:
            player.model.load_state_dict(saved_state)
            player.cx = Variable(torch.zeros(1, 512), volatile=True)
            player.hx = Variable(torch.zeros(1, 512), volatile=True)
            if player.starter:
                player = player_start(player, train=False)
        else:
            player.cx = Variable(player.cx.data, volatile=True)
            player.hx = Variable(player.hx.data, volatile=True)

        player, reward = player_act(player, train=False)
        reward_sum += reward

        if not player.done:
            if player.current_life > player.info['ale.lives']:
                player.flag = True
                player.current_life = player.info['ale.lives']
            else:
                player.current_life = player.info['ale.lives']
                player.flag = False
        if player.starter and player.flag:
            player = player_start(player, train=False)

        if player.done:
            num_tests += 1
            reward_total_sum += reward_sum
            reward_mean = reward_total_sum / num_tests
            log['{}_mon_log'.format(args.env)].info(
                "reward sum: {0}, reward mean: {1:.4f}".format(
                    reward_sum, reward_mean))

            break
