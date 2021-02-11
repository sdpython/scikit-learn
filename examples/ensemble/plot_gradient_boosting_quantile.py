"""
=====================================================
Prediction Intervals for Gradient Boosting Regression
=====================================================

This example shows how quantile regression can be used to create prediction
intervals.
"""
# %%
# Generate some data for a synthetic regression problem by applying the f
# function to uniformly sampled random inputs.
import numpy as np
from sklearn.model_selection import train_test_split


def f(x):
    """The function to predict."""
    return x * np.sin(x)


rng = np.random.RandomState(42)
X = np.atleast_2d(rng.uniform(0, 10.0, size=1000)).T
X = X.astype(np.float32)
y = f(X).ravel()

# %%
# To make the problem interesting, add centered `log-normal distributed
# <https://en.wikipedia.org/wiki/Log-normal_distribution>`_ random noise to the
# target variable.
#
# The lognormal distribution is very skewed, meaning that it is likely to get
# large outliers but impossible to observe small outliers.
sigma = 1.2
noise = rng.lognormal(sigma=sigma, size=y.shape) - np.exp(sigma ** 2 / 2)
y += noise

# %%
# Split into train, test datasets:
X_train, X_test, y_train, y_test = train_test_split(X, y)

# %%
# Fitting non-linear quantile and least squares regressors
# --------------------------------------------------------
#
# Fit gradient boosting models trained with the quantile loss and
# alpha=0.05, 0.5, 0.95.
#
# The models obtained for alpha=0.05 and alpha=0.95 produce a 90% confidence
# interval (95% - 5% = 90%).
#
# The model trained with alpha=0.5 produces a regression of the median: on
# average, there should be the same number of target observations above and
# below the predicted values.
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import pinball_loss, mean_squared_error


all_models = {}
common_params = dict(
    learning_rate=0.05,
    n_estimators=250,
    max_depth=2,
    min_samples_leaf=9,
    min_samples_split=9,
)
for alpha in [0.05, 0.5, 0.95]:
    gbr = GradientBoostingRegressor(loss='quantile', alpha=alpha,
                                    **common_params)
    all_models["q %1.2f" % alpha] = gbr.fit(X_train, y_train)

# %%
# For the sake of comparison, also fit a baseline model trained with the usual
# least squares loss (ls), also known as the mean squared error (MSE).
gbr_ls = GradientBoostingRegressor(loss='ls', **common_params)
all_models["ls"] = gbr_ls.fit(X_train, y_train)

# %%
# Create an evenly spaced set of input values spanning the [0, 10] range.
xx = np.atleast_2d(np.linspace(0, 10, 1000)).T
xx = xx.astype(np.float32)

# %%
# Plot the true function (expected mean), the prediction of the conditional
# mean (least squares loss), the conditional median and the conditional 90%
# interval (from 5th to 95th conditional percentiles).
import matplotlib.pyplot as plt


y_pred = all_models['ls'].predict(xx)
y_lower = all_models['q 0.05'].predict(xx)
y_upper = all_models['q 0.95'].predict(xx)
y_med = all_models['q 0.50'].predict(xx)

fig = plt.figure()
plt.plot(xx, f(xx), 'g:', label=r'$f(x) = x\,\sin(x)$')
plt.plot(X_test, y_test, 'b.', markersize=10, label='Test observations')
plt.plot(xx, y_med, 'r-', label='Predicted median', color="orange")
plt.plot(xx, y_pred, 'r-', label='Predicted mean')
plt.plot(xx, y_upper, 'k-')
plt.plot(xx, y_lower, 'k-')
plt.fill_between(xx.ravel(), y_lower, y_upper, alpha=0.5,
                 label='Predicted 90% interval')
plt.xlabel('$x$')
plt.ylabel('$f(x)$')
plt.ylim(-10, 20)
plt.legend(loc='upper left')
plt.show()

# %%
# Note that the predicted median is on average below the predicted mean as the
# noise is skewed towards high values (large outliers). Also note that the
# median estimate is smoother because of its natural robustness to outliers.
#
# Also observe that the inductive bias of gradient boosting trees is
# unfortunately preventing our 0.05 quantile to fully capture the sinoisoidal
# shape of the signal, in particular around x=8. Tuning hyper-parameters can
# reduce this effect as shown in the last part of this notebook.
#
# Analysis of the error metrics
# -----------------------------
#
# Measure the models with :func:`mean_square_error` and :func:`pinball_loss`
# metrics on the training dataset.
from pandas import DataFrame

results = []
for name, gbr in sorted(all_models.items()):
    metrics = {'model': name}
    y_pred = gbr.predict(X_train)
    for alpha in [0.05, 0.5, 0.95]:
        metrics["pbl=%1.2f" % alpha] = pinball_loss(
            y_train, y_pred, alpha=alpha)
    metrics['MSE'] = mean_squared_error(y_train, y_pred)
    results.append(metrics)
DataFrame(results).set_index('model')

# %%
# One column shows all models evaluated by the same metric. The minimum number
# on a column should be obtained when the model is trained and measured with
# the same metric. This should be always the case on the training set if the
# training converged.
#
# Note that because the target noise is skewed by the presence of large
# outliers, the expected conditional mean and conditional median are
# signficiantly different and therefore one could not use the least squares
# model get a good estimation of the conditional median nor the converse.
#
# If the target distribution were symmetric and had no outliers (e.g. with
# a Gaussian noise), then median estimator and the least squares estimator
# would have yielded similar predictions.
#
# We then do the same on the test set.
results = []
for name, gbr in sorted(all_models.items()):
    metrics = {'model': name}
    y_pred = gbr.predict(X_test)
    for alpha in [0.05, 0.5, 0.95]:
        metrics["pbl=%1.2f" % alpha] = pinball_loss(
            y_test, y_pred, alpha=alpha)
    metrics['MSE'] = mean_squared_error(y_test, y_pred)
    results.append(metrics)
DataFrame(results).set_index('model')

# %%
# Errors are higher meaning the models slightly overfitted the data. It still
# shows the minimum of a metric is obtained when the model is trained by
# minimizing this same metric.
#
# Tuning the hyper-parameters of the quantile regressors
# ------------------------------------------------------
#
# In the plot above, we observed that the 5th percentile regressor seems to
# underfit and could not adapt to sinusoidal shape of the signal.
#
# The hyper-parameters of the model were approximately hand-tuned for the
# median regressor and there is no reason than the same hyper-parameters are
# suitable for the 5th percentile regressor.
#
# To confirm this hypothesis, we tuned the hyper-parameters of a new regressor
# of the 5th percentile by selecting the best model parameters by
# cross-validation on the pinball loss with alpha=0.05:

# %%
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import make_scorer


param_grid = dict(
    learning_rate=[0.01, 0.05, 0.1],
    n_estimators=[100, 150, 200, 250, 300],
    max_depth=[2, 5, 10, 15, 20],
    min_samples_leaf=[1, 5, 10, 20, 30, 50],
    min_samples_split=[2, 5, 10, 20, 30, 50],
)
alpha = 0.05
neg_pinball_loss_05p_scorer = make_scorer(
    pinball_loss,
    alpha=alpha,
    greater_is_better=False,  # maximize the negative loss
)
search_05p = RandomizedSearchCV(
    GradientBoostingRegressor(loss="quantile", alpha=alpha),
    param_grid,
    n_iter=10,  # increase this if computational budget allows
    scoring=neg_pinball_loss_05p_scorer,
    n_jobs=2,
    random_state=0,
).fit(X_train, y_train)
search_05p.best_params_

# %%
# We observe that the search procedure identifies that deeper trees are needed
# to get a good fit for the 5th percentile regressor. Deeper trees are more
# expressive and less likely to underfit.
#
# Let's do another hyper-parameter tuning session for the 95th percentile
# regressor. We need to redefine the `scoring` metric used to select the best
# model, along with adjusting the alpha parameter of the inner gradient
# boosting estimator itself:
from sklearn.base import clone

alpha = 0.95
neg_pinball_loss_95p_scorer = make_scorer(
    pinball_loss,
    alpha=alpha,
    greater_is_better=False,  # maximize the negative loss
)
search_95p = clone(search_05p).set_params(
    estimator__alpha=alpha,
    scoring=neg_pinball_loss_95p_scorer,
)
search_95p.fit(X_train, y_train)
search_95p.best_params_

# %%
# This time, shallower trees are selected and lead to a more constant piecewise
# and therefore more robust estimation of the 95th percentile. This is
# beneficial as it avoids overfitting the large outliers of the log-normal
# additive noise.
#
# We can confirm this intuition by displaying the predicted 90% confidence
# interval comprised by the predictions of those two tuned quantile regressors:
# the prediction of the upper 95th percentile has a much coarser shape than the
# prediction of the lower 5th percentile:
y_lower = search_05p.predict(xx)
y_upper = search_95p.predict(xx)

fig = plt.figure()
plt.plot(xx, f(xx), 'g:', label=r'$f(x) = x\,\sin(x)$')
plt.plot(X_test, y_test, 'b.', markersize=10, label='Test observations')
plt.plot(xx, y_upper, 'k-')
plt.plot(xx, y_lower, 'k-')
plt.fill_between(xx.ravel(), y_lower, y_upper, alpha=0.5,
                 label='Predicted 90% interval')
plt.xlabel('$x$')
plt.ylabel('$f(x)$')
plt.ylim(-10, 20)
plt.legend(loc='upper left')
plt.title("Prediction with tuned hyper-parameters")
plt.show()
