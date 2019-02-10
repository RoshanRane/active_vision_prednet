# Active vision in PredNet

### Introduction :
In this project, we will study different way to implement an "Active vision" technique on the PredNet architecture (https://coxlab.github.io/prednet/)

The PredNet model is a deep learning model that is inspired by the neuroscientific theory of Predictive coding. The model is trained to predict the next frame in videos. We will use the following video action-classification datasets : https://20bn.com/datasets/something-something/v2

### Motivation : 
Working with videos is very computationally expensive and using active vision techniques to 'actively' select and process smaller portions of the video at a time could turnout to be very useful.
Also we believe that 'actively' deciding the sample of the video through the course of learning would result in the model learning a richer representation of the video as a whole.
 
### Sub-tasks :
There are a bunch of possible working directions in this project :

(1) Study the different techniques of implementing Active Vision in PredNet.

I could think of the following techniques - saccadic vision-like, fovea-like, using probabilistic saliency filters, soft attention layers, controlling dropout/dropconnect, control inception layer.

(2) Try to implement saccadic-vision-like system in the PredNet's top-down.

(3) Try to implement probabilistic saliency filters in the PredNet's top-down.

(4) Try using soft-attention in the PredNet's top-down.

(5) Study this problem as a Reinforcement learning problem and argue if the problems faced by today's RL techniques are also applicable here ?
It goes something like this - the top-down makes a series of choices /actions through the time span of the video. These actions could be, for example, selecting the next region to focus on in a saccadic-based model or fovea-based model. Each action is selected conditional on the previous sequence of actions and inputs just like any other RL problem. At the end of the video the model predicts the action class of the video. A policy gradient then helps the model to learn the right policy (the sequence of actions that lead to correct action classification of the video) from the wrong ones.

### Architecture :
Vanilla PredNet            |  Active PredNet
:-------------------------:|:-------------------------:
<img src="https://github.com/RoshanRane/active_vision_prednet/blob/master/PredNet_Vanilla.jpg"  height="450" width="400"/> | <img src="https://github.com/RoshanRane/active_vision_prednet/blob/master/PredNet_active.png"  height="450" width="400" align="right"/>
