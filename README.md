# Safe Reinforcement Learning via Episodic Control
  * SEC is based on [tianshou](https://tianshou.readthedocs.io/en/master/index.html) platform and safe RL algorithm benchmark [FSRL](https://fsrl.readthedocs.io/). Please refer the original repo for details.


## Requirements

  * Ubuntu 20.04, cuda 12.2, nvidia driver 535.86.05, and python 3.8.5

## Install

  * pip3 install -r requirements.txt

## Execution:

    The implementation of episodic memory, state measurement, and reward shaping are in:
        
        * fsrl/data/abstracter.py

## Execution:
  
  * Example:

        python  train_ddpgl_agent.py --task SafetyBallCircle-v0 --epoch 50  --episodic True --episodic_step 3 

  * Execute the scripts:
         
        bash scripts/train_navigation_episodic.sh

## Experiment results:

  * Data will be automatically saved into ./result