import theano
from theano import tensor
import numpy

from blocks.algorithms import Momentum, AdaDelta, RMSProp, CompositeRule, BasicMomentum, RemoveNotFinite, StepClipping
from blocks.bricks import Tanh, Softmax, Linear, MLP, Rectifier
from blocks.bricks.recurrent import LSTM
from blocks.bricks.lookup import LookupTable
from blocks.initialization import IsotropicGaussian, Constant

from blocks.filter import VariableFilter
from blocks.roles import WEIGHT
from blocks.graph import ComputationGraph, apply_noise, apply_dropout

name = 'MLP'
couches = 3
input_dim = 1
out_dim = 1
hidden_dim = 50
activation_functi0n = Tanh() 
activation_function_name = 'Tanh' 
batch_size = 400 
w_noise_std = 0
i_dropout = 0
proportion_train = 0.9
algo = 'RMS'
learning_rate_value = 1e-5
momentum_value = 0.9
decay_rate_value = 0
StepClipping_value = 2

step_rule = CompositeRule([RMSProp(learning_rate=learning_rate_value), #decay_rate=decay_rate_value,
                          BasicMomentum(momentum=momentum_value),
                          StepClipping(StepClipping_value)])
print_freq = 1000
valid_freq = 10000
save_freq = 10000

class Model():
    def __init__(self):
        inp = tensor.tensor3('input')[:,:,0]
        target = tensor.matrix('target')
        target = target.reshape((target.shape[0],))
        product = tensor.lvector('product')
        missing = tensor.eq(inp, 0)
        train_input_mean = 1470614.1
        train_input_std = 3256577.0

        trans_1 = tensor.concatenate((inp[:,1:],tensor.zeros((inp.shape[0],1))), axis=1) 
        trans_2 = tensor.concatenate((tensor.zeros((inp.shape[0],1)), inp[:,:-1]), axis=1) 
        inp = tensor.switch(missing,(trans_1+trans_2)/2, inp)

        lookup = LookupTable(length = 352, dim=hidden_dim)
        product_embed= lookup.apply(product)

        salut = tensor.concatenate((inp, missing),axis = 1)
        
        linear = Linear(input_dim=108, output_dim=hidden_dim,
                        name="MLP_in")
        inter = linear.apply(salut)
        inter = inter + product_embed

        mlp1 = MLP(activations=[Rectifier(),Rectifier(),Rectifier()], 
                    dims=[hidden_dim,hidden_dim,hidden_dim,hidden_dim],
                        name="premier")
        inter1 = mlp1.apply(inter)

        linear2= Linear(input_dim = hidden_dim, output_dim = out_dim,
                       name="ouput_linear")

        pred = linear2.apply(inter1)*train_input_std + train_input_mean
        pred = pred.reshape((product.shape[0],))

        cost = tensor.mean(abs((pred-target)/target))
        # Initialize all bricks
        for brick in [linear, linear2, mlp1, lookup]:
            brick.weights_init = IsotropicGaussian(0.1)
            brick.biases_init = Constant(0.)
            brick.initialize()

        # Apply noise and dropout
        cg = ComputationGraph([cost])
        if w_noise_std > 0:
            noise_vars = VariableFilter(roles=[WEIGHT])(cg)
            cg = apply_noise(cg, noise_vars, w_noise_std)
        if i_dropout > 0:
            cg = apply_dropout(cg, [inter1], i_dropout)
        [cost_reg] = cg.outputs
        cost_reg += 1e-20

        if cost_reg is not cost:
            self.cost = cost
            self.cost_reg = cost_reg

            cost_reg.name = 'cost_reg'
            cost.name = 'cost'

            self.sgd_cost = cost_reg

            self.monitor_vars = [[cost, cost_reg]]
        else:
            self.cost = cost
            cost.name = 'cost'

            self.sgd_cost = cost

            self.monitor_vars = [[cost]]

        self.pred = pred
        pred.name = 'pred'