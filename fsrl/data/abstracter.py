import os,sys
import copy
import numpy as np
import pickle, joblib, time
from .interfaces import grid_abs_analysis
from .interfaces import Grid
from multiprocessing import Process  
import scipy.stats as stats
from multiprocessing import Queue
import json

class ScoreInspector:
    
    def __init__(self, step, grid_num):

        self.step = step
        self.grid_num = grid_num
        self.raw_state_dim = 128
        self.state_dim = 24
        self.state_min = 0
        self.state_max = 1
        self.basic_states = None
        self.basic_states_times = None
        self.basic_states_scores = None
        self.basic_states_returns = None
     
        self.score_avg = None
        self.pcaModel = None
        self.performance_list = []
        self.avg_performance_list = []

        
        #self.QUEUE_LEN
        self.s_token = Queue(10)
        self.r_token = Queue(10)
        
        self.setup()


    
    def setup(self):

        self.project_matrix = np.random.uniform(-1,1,(self.raw_state_dim,self.state_dim))
        self.min_state = np.dot(np.array([self.state_min for i in range(self.raw_state_dim)]), self.project_matrix)
        self.max_state = np.dot(np.array([self.state_max for i in range(self.raw_state_dim)]), self.project_matrix)

    
        self.min_avg_return = 0.001
        self.max_avg_return = 1
        self.min_avg_cost   = 0.001
        self.max_avg_cost   = 1

        #self.scores = scores
        self.score_avg = 0
        
        #self.states_info = self.setup_score_dict(states, times, returns, scores, values)
        self.states_info = dict()
        
        #self.pcaModel = joblib.load(config.PCA_MODEL_PATH)
        print(self.min_state, self.max_state, self.grid_num)
        self.grid = Grid(self.min_state, self.max_state, self.grid_num)   

    def save(self, env_name):
        with open(env_name + '.json', 'w') as f:
            json.dump(self.states_info, f)

    def discretize_states(self, con_states):
        abs_states = self.grid.state_abstract(con_states)
        return abs_states
    
    def inquery(self, pattern):
        if pattern in self.states_info.keys():
            return self.states_info[pattern]['score'], self.states_info[pattern]['time'] 
        else:
            return None, None

    def sync_scores(self):
        if self.s_token.qsize() > 0:

            new_states_info, min_avg_return, max_avg_return, min_avg_cost, max_avg_cost = self.s_token.get()
            
            if min_avg_return < self.min_avg_return:
                self.min_avg_return = min_avg_return
            if max_avg_return > self.max_avg_return:
                self.max_avg_return = max_avg_return
            if min_avg_cost < self.min_avg_cost:
                self.min_avg_cost = min_avg_cost
            if max_avg_cost > self.max_avg_cost:
                self.max_avg_cost = max_avg_cost

            self.states_info.update(new_states_info)
            self.score_avg = np.mean([self.states_info[abs_state]['score'] for abs_state in self.states_info.keys()])            
            
    
    def start_pattern_abstract(self, con_states, rewards, costs):

        con_states = np.array(con_states)
        con_states = con_states[:,:self.state_dim]
        t = Process(target = self.pattern_abstract, args = (con_states, rewards, costs))
        t.daemon = True
        t.start()

    def compute_score(self, returns, costs):
        return np.clip(returns/costs, 0, 10)

    def pattern_abstract(self, con_states, rewards, costs):

        abs_states = self.discretize_states(con_states)
        min_avg_return = self.min_avg_return
        max_avg_return = self.max_avg_return

        min_avg_cost   = self.min_avg_cost
        max_avg_cost   = self.max_avg_cost

        new_states_info = dict()
        return_normal_scale = self.max_avg_return - self.min_avg_return
        cost_normal_scale = self.max_avg_cost - self.min_avg_cost

        returns = sum(rewards)
        costs   = sum(costs)

        for i in range(len(abs_states)):
            if i + self.step >= len(abs_states):
                break
                
            
            if returns < self.min_avg_return:
                min_avg_return = returns
            if returns > self.max_avg_return:
                max_avg_return = returns

            if costs < self.min_avg_cost:
                min_avg_cost = costs
            if costs > self.max_avg_cost:
                max_avg_cost = costs

            pattern = abs_states[i:i+self.step]
            pattern = '-'.join(pattern)

            if pattern in self.states_info.keys():
                new_states_info[pattern] = self.states_info[pattern]
                new_states_info[pattern]['returns'] += returns
                new_states_info[pattern]['costs'] += costs
                new_states_info[pattern]['time'] += 1
                average_return = new_states_info[pattern]['returns'] / new_states_info[pattern]['time']
                average_cost = new_states_info[pattern]['costs'] / new_states_info[pattern]['time']
                new_states_info[pattern]['return_score'] = (average_return - self.min_avg_return)  / return_normal_scale
                new_states_info[pattern]['cost_score']   = (average_cost - self.min_avg_cost)  / cost_normal_scale + 0.01
                score = np.clip(new_states_info[pattern]['return_score'] / new_states_info[pattern]['cost_score'], 0, 10)
                new_states_info[pattern]['score'] =  score
            else:
                new_states_info[pattern] = {}
                new_states_info[pattern]['returns'] = returns
                new_states_info[pattern]['costs'] = costs
                new_states_info[pattern]['time'] = 1
                new_states_info[pattern]['return_score'] = (returns - self.min_avg_return)  / return_normal_scale
                new_states_info[pattern]['cost_score']   = (costs - self.min_avg_cost)  / cost_normal_scale + 0.01
                score = np.clip(new_states_info[pattern]['return_score'] / new_states_info[pattern]['cost_score'], 0, 10)
                new_states_info[pattern]['score'] =  score

        self.s_token.put((new_states_info, min_avg_return, max_avg_return, min_avg_cost, max_avg_cost))

    


class Abstracter:
    
    def __init__(self, step, epsilon):
        self.con_states = []
        self.con_values = []
        self.con_reward = []
        self.con_cost   = []
        self.con_dones  = []
        self.step = step
        self.epsilon = epsilon
        self.inspector = None

    def dim_reduction(self, con_state):
        small_state = np.dot(con_state, self.inspector.project_matrix)
        return  small_state

        
    def append(self, con_state, reward, cost, done):

        self.con_states.append(con_state)
        self.con_reward.append(reward)
        self.con_cost.append(cost)
        self.con_dones.append(done)

        if done:
            self.con_states = self.dim_reduction(self.con_states)
            self.inspector.start_pattern_abstract(self.con_states, self.con_reward, self.con_cost)
            self.clear()
    
    def clear(self):
        self.con_states = []
        self.con_reward = []
        self.con_cost   = []
        self.con_dones  = []
    
    def handle_pattern(self,abs_pattern,rewards):
        
        if len(abs_pattern) != self.step:
            return rewards[0]
        pattern = '-'.join(abs_pattern)
        score, time = self.inspector.inquery(pattern)
        
        if score != None:
            if  time > 0:
                delta = (score - self.inspector.score_avg) * self.epsilon
                print(
                    pattern, 
                    score, 
                    self.inspector.score_avg, 
                    self.inspector.states_info[pattern]["return_score"], 
                    self.inspector.states_info[pattern]["cost_score"], 
                    rewards[0], 
                    rewards[0] + delta
                )
                rewards[0] += delta
                
        return rewards[0]



    def reward_shaping(self, state_list, reward_list, cost_list):

        state_list = self.dim_reduction(state_list)
        
        abs_states = self.inspector.discretize_states(state_list)
        
        shaping_reward_list = copy.deepcopy(reward_list)

        for i in range(len(abs_states) - self.step):

            target_patterns = abs_states[i:i+self.step]
            target_rewards = reward_list[i:i+self.step]
            target_costs   = cost_list[i:i+self.step]

            shaped_reward = self.handle_pattern(target_patterns, target_rewards)
            shaping_reward_list[i] = shaped_reward
        
        shaping_reward_list = np.array(shaping_reward_list)
        return shaping_reward_list