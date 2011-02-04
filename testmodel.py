from model import HTK_model,TrainLogger







model = HTK_model()

model.re_estimate()
#TrainLogger.a.pop()
model.create_from_proto()
model.split_mixtures(2)

print TrainLogger.a

