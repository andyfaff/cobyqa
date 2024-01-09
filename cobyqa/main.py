import warnings

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, NonlinearConstraint, OptimizeResult

from .framework import TrustRegion
from .problem import ObjectiveFunction, BoundConstraints, LinearConstraints, NonlinearConstraints, Problem
from .utils import MaxEvalError, TargetSuccess, FeasibleSuccess, exact_1d_array
from .settings import ExitStatus, Options, DEFAULT_OPTIONS, PRINT_OPTIONS


def minimize(fun, x0, args=(), bounds=None, constraints=(), callback=None, options=None):
    r"""
    Minimize a scalar function using the COBYQA method.

    The COBYQA method is a derivative-free optimization method designed to solve
    general nonlinear optimization problems. A complete description of the
    method is given in [3]_.

    Parameters
    ----------
    fun : {callable, None}
        Objective function to be minimized.

            ``fun(x, *args) -> float``

        where ``x`` is an array with shape (n,) and `args` is a tuple. If None,
        the objective function is assumed to be the zero function.
    x0 : array_like, shape (n,)
        Initial guess.
    args : tuple, optional
        Extra arguments passed to the objective function.
    bounds : {`scipy.optimize.Bounds`, array_like, shape (n, 2)}, optional
        Bound constraints of the problem. It can be one of the cases below.

        #. An instance of `scipy.optimize.Bounds`. For the time being, the
           argument ``keep_feasible`` is disregarded.
        #. An array with shape (n, 2). The bound constraints for ``x[i]`` are
           ``bounds[i][0] <= x[i] <= bounds[i][1]``. Set ``bounds[i][0]`` to
           :math:`-\infty` if there is no lower bound, and set ``bounds[i][1]``
           to :math:`\infty` if there is no upper bound.

    constraints : {`scipy.optimize.LinearConstraint`, `scipy.optimize.NonlinearConstraint`, dict, list}, optional
        General constraints of the problem. It can be one of the cases below.

        #. An instance of `scipy.optimize.LinearConstraint`. The argument
           ``keep_feasible`` is disregarded.
        #. An instance of `scipy.optimize.NonlinearConstraint`. The arguments
           ``jac``, ``hess``, ``keep_feasible``, ``finite_diff_rel_step``, and
           ``finite_diff_jac_sparsity`` are disregarded.
        #. A dictionary with fields:

            type : {'eq', 'ineq'}
                Whether the constraint is an equality ``fun(x, *args) = 0`` or
                an inequality ``fun(x, *args) >= 0``.
            fun : callable
                Constraint function.
            args : tuple, optional
                Extra arguments passed to the constraint function.

        #. A list, each of whose elements are described in the cases above.

    callback : callable, optional
        A callback executed at each objective function evaluation. The method
        terminates if a ``StopIteration`` exception is raised by the callback
        function. Its signature can be one of the following:

            ``callback(intermediate_result)``

        where ``intermediate_result`` is a keyword parameter that contains an
        instance of `scipy.optimize.OptimizeResult`, with attributes ``x``
        and ``fun``, being the point at which the objective function is
        evaluated and the value of the objective function, respectively. The
        name of the parameter must be ``intermediate_result`` for the callback
        to be passed an instance of `scipy.optimize.OptimizeResult`.

        Alternatively, the callback function can have the signature:

            ``callback(xk)``

        where ``xk`` is the point at which the objective function is evaluated.
        Introspection is used to determine which of the signatures to invoke.
    options : dict, optional
        Options passed to the solver. Accepted keys are:

            disp : bool, optional
                Whether to print information about the optimization procedure.
            maxfev : int, optional
                Maximum number of function evaluations.
            maxiter : int, optional
                Maximum number of iterations.
            target : float, optional
                Target on the objective function value. The optimization
                procedure is terminated when the objective function value of a
                nearly feasible point is less than or equal to this target.
            feasibility_tol : float, optional
                Tolerance on the constraint violation.
            radius_init : float, optional
                Initial trust-region radius. Typically, this value should be in
                the order of one tenth of the greatest expected change to the
                variables.
            radius_final : float, optional
                Final trust-region radius. It should indicate the accuracy
                required in the final values of the variables.
            nb_points : int, optional
                Number of interpolation points used to build the quadratic
                models of the objective and constraint functions.
            scale : bool, optional
                Whether to scale the variables according to the bounds.
            filter_size : int, optional
                Maximum number of points in the filter. The filter is used to
                select the best point returned by the optimization procedure.
            store_history : bool, optional
                Whether to store the history of the function evaluations.
            history_size : int, optional
                Maximum number of function evaluations to store in the history.
            debug : bool, optional
                Whether to perform additional checks. This option should be
                used only for debugging purposes and is highly discouraged to
                general users.

    Returns
    -------
    `scipy.optimize.OptimizeResult`
        Result of the optimization procedure, with the following fields:

            message : str
                Description of the cause of the termination.
            success : bool
                Whether the optimization procedure terminated successfully.
            status : int
                Termination status of the optimization procedure.
            x : `numpy.ndarray`, shape (n,)
                Solution point.
            fun : float
                Objective function value at the solution point.
            maxcv : float
                Maximum constraint violation at the solution point.
            nfev : int
                Number of function evaluations.
            nit : int
                Number of iterations.

        If ``store_history`` is True, the result also has the following fields:

            fun_history : `numpy.ndarray`, shape (nfev,)
                History of the objective function values.
            maxcv_history : `numpy.ndarray`, shape (nfev,)
                History of the maximum constraint violations.

        A description of the termination statuses is given below.

        .. list-table::
            :widths: 25 75
            :header-rows: 1

            * - Exit status
              - Description
            * - 0
              - The lower bound for the trust-region radius has been reached.
            * - 1
              - The target objective function value has been reached.
            * - 2
              - All variables are fixed by the bound constraints.
            * - 3
              - The callback requested to stop the optimization procedure.
            * - 4
              - The feasibility problem received has been solved successfully.
            * - 5
              - The maximum number of function evaluations has been exceeded.
            * - 6
              - The maximum number of iterations has been exceeded.
            * - -1
              - The bound constraints are infeasible.
            * - -2
              - A linear algebra error occurred.

    References
    ----------
    .. [1] J. Nocedal and S. J. Wright. *Numerical Optimization*. Springer Ser.
       Oper. Res. Financ. Eng. Springer, New York, NY, USA, second edition,
       2006. `doi:10.1007/978-0-387-40065-5
       <https://doi.org/10.1007/978-0-387-40065-5>`_.
    .. [2] M. J. D. Powell. A direct search optimization method that models the
       objective and constraint functions by linear interpolation. In S. Gomez
       and J.-P. Hennart, editors, *Advances in Optimization and Numerical
       Analysis*, volume 275 of Math. Appl., pages 51--67. Springer, Dordrecht,
       Netherlands, 1994. `doi:10.1007/978-94-015-8330-5_4
       <https://doi.org/10.1007/978-94-015-8330-5_4>`_.
    .. [3] T. M. Ragonneau. *Model-Based Derivative-Free Optimization Methods
       and Software*. PhD thesis, Department of Applied Mathematics, The Hong
       Kong Polytechnic University, Hong Kong, China, 2022. URL:
       https://theses.lib.polyu.edu.hk/handle/200/12294.

    Examples
    --------
    To demonstrate how to use `minimize`, we first minimize the Rosenbrock
    function implemented in `scipy.optimize` in an unconstrained setting.

    .. testsetup::

        import numpy as np
        np.set_printoptions(precision=3, suppress=True)

    >>> from cobyqa import minimize
    >>> from scipy.optimize import rosen

    To solve the problem using COBYQA, run:

    >>> x0 = [1.3, 0.7, 0.8, 1.9, 1.2]
    >>> res = minimize(rosen, x0)
    >>> res.x
    array([1., 1., 1., 1., 1.])

    To see how bound and constraints are handled using `minimize`, we solve
    Example 16.4 of [1]_, defined as

    .. math::

        \begin{aligned}
            \min_{x \in \mathbb{R}^2}   & \quad (x_1 - 1)^2 + (x_2 - 2.5)^2\\
            \text{s.t.}                 & \quad -x_1 + 2x_2 \le 2,\\
                                        & \quad x_1 + 2x_2 \le 6,\\
                                        & \quad x_1 - 2x_2 \le 2,\\
                                        & \quad x_1 \ge 0,\\
                                        & \quad x_2 \ge 0.
        \end{aligned}

    >>> import numpy as np
    >>> from scipy.optimize import Bounds, LinearConstraint

    Its objective function can be implemented as:

    >>> def fun(x):
    ...     return (x[0] - 1.0) ** 2.0 + (x[1] - 2.5) ** 2.0

    This problem can be solved using `minimize` as:

    >>> x0 = [2.0, 0.0]
    >>> bounds = Bounds([0.0, 0.0], np.inf)
    >>> constraints = LinearConstraint([[-1.0, 2.0], [1.0, 2.0], [1.0, -2.0]], -np.inf, [2.0, 6.0, 2.0])
    >>> res = minimize(fun, x0, bounds=bounds, constraints=constraints)
    >>> res.x
    array([1.4, 1.7])

    Finally, to see how nonlinear constraints are handled, we solve Problem (F)
    of [2]_, defined as

    .. math::

        \begin{aligned}
            \min_{x \in \mathbb{R}^2}   & \quad -x_1 - x_2\\
            \text{s.t.}                 & \quad x_1^2 - x_2 \le 0,\\
                                        & \quad x_1^2 + x_2^2 \le 1.
        \end{aligned}

    >>> from scipy.optimize import NonlinearConstraint

    Its objective and constraint functions can be implemented as:

    >>> def fun(x):
    ...     return -x[0] - x[1]
    >>>
    >>> def cub(x):
    ...     return [x[0] ** 2.0 - x[1], x[0] ** 2.0 + x[1] ** 2.0]

    This problem can be solved using `minimize` as:

    >>> x0 = [1.0, 1.0]
    >>> constraints = NonlinearConstraint(cub, -np.inf, [0.0, 1.0])
    >>> res = minimize(fun, x0, constraints=constraints)
    >>> res.x
    array([0.707, 0.707])
    """
    # Get basic options that are needed for the initialization.
    if options is None:
        options = {}
    else:
        options = dict(options)
    verbose = options.get(Options.VERBOSE, DEFAULT_OPTIONS[Options.VERBOSE])
    verbose = bool(verbose)
    feasibility_tol = options.get(Options.FEASIBILITY_TOL, DEFAULT_OPTIONS[Options.FEASIBILITY_TOL])
    feasibility_tol = float(feasibility_tol)
    scale = options.get(Options.SCALE, DEFAULT_OPTIONS[Options.SCALE])
    scale = bool(scale)
    store_history = options.get(Options.STORE_HISTORY, DEFAULT_OPTIONS[Options.STORE_HISTORY])
    store_history = bool(store_history)
    if Options.HISTORY_SIZE in options and options[Options.HISTORY_SIZE] <= 0:
        raise ValueError('The size of the history must be positive.')
    history_size = options.get(Options.HISTORY_SIZE, DEFAULT_OPTIONS[Options.HISTORY_SIZE])
    history_size = int(history_size)
    if Options.FILTER_SIZE in options and options[Options.FILTER_SIZE] <= 0:
        raise ValueError('The size of the filter must be positive.')
    filter_size = options.get(Options.FILTER_SIZE, DEFAULT_OPTIONS[Options.FILTER_SIZE])
    filter_size = int(filter_size)
    debug = options.get(Options.DEBUG, DEFAULT_OPTIONS[Options.DEBUG])
    debug = bool(debug)

    # Initialize the objective function.
    if not isinstance(args, tuple):
        args = (args,)
    obj = ObjectiveFunction(fun, verbose, debug, *args)

    # Initialize the bound constraints.
    if not hasattr(x0, '__len__'):
        x0 = [x0]
    n_orig = len(x0)
    bounds = BoundConstraints(_get_bounds(bounds, n_orig))

    # Initialize the constraints.
    linear_constraints, nonlinear_constraints = _get_constraints(constraints)
    linear = LinearConstraints(linear_constraints, n_orig, debug)
    nonlinear = NonlinearConstraints(nonlinear_constraints, verbose, debug)

    # Initialize the problem (and remove the fixed variables).
    pb = Problem(obj, x0, bounds, linear, nonlinear, callback, feasibility_tol, scale, store_history, history_size, filter_size, debug)

    # Set the default options.
    _set_default_options(options, pb.n)

    # Initialize the models and skip the computations whenever possible.
    if not pb.bounds.is_feasible:
        # The bound constraints are infeasible.
        return _build_result(pb, 0.0, False, ExitStatus.INFEASIBLE_ERROR, 0, options)
    elif pb.n == 0:
        # All variables are fixed by the bound constraints.
        return _build_result(pb, 0.0, True, ExitStatus.FIXED_SUCCESS, 0, options)
    if verbose:
        print('Starting the optimization procedure.')
        print(f'Initial trust-region radius: {options[Options.RHOBEG]}.')
        print(f'Final trust-region radius: {options[Options.RHOEND]}.')
        print(f'Maximum number of function evaluations: {options[Options.MAX_EVAL]}.')
        print(f'Maximum number of iterations: {options[Options.MAX_ITER]}.')
        print()
    try:
        framework = TrustRegion(pb, options)
    except TargetSuccess:
        # The target on the objective function value has been reached
        return _build_result(pb, 0.0, True, ExitStatus.TARGET_SUCCESS, 0, options)
    except StopIteration:
        # The callback raised a StopIteration exception.
        return _build_result(pb, 0.0, True, ExitStatus.CALLBACK_SUCCESS, 0, options)
    except FeasibleSuccess:
        # The feasibility problem has been solved successfully.
        return _build_result(pb, 0.0, True, ExitStatus.FEASIBLE_SUCCESS, 0, options)
    except MaxEvalError:
        # The maximum number of function evaluations has been exceeded.
        return _build_result(pb, 0.0, False, ExitStatus.MAX_ITER_WARNING, 0, options)
    except np.linalg.LinAlgError:
        # The construction of the initial interpolation set failed.
        return _build_result(pb, 0.0, False, ExitStatus.LINALG_ERROR, 0, options)

    # Start the optimization procedure.
    success = False
    n_iter = 0
    k_new = None
    n_short_steps = 0
    n_very_short_steps = 0
    n_alt_models = 0
    while True:
        # Stop the optimization procedure if the maximum number of iterations
        # has been exceeded. We do not write the main loop as a for loop because
        # we want to access the number of iterations outside the loop.
        if n_iter >= options[Options.MAX_ITER]:
            status = ExitStatus.MAX_ITER_WARNING
            break
        n_iter += 1

        # Update the point around which the quadratic models are built.
        if np.linalg.norm(framework.x_best - framework.models.interpolation.x_base) >= 10.0 * framework.radius:
            framework.shift_x_base(options)

        # Evaluate the trial step.
        radius_save = framework.radius
        normal_step, tangential_step = framework.get_trust_region_step(options)
        step = normal_step + tangential_step
        s_norm = np.linalg.norm(step)

        # If the trial step is too short, we do not attempt to evaluate the
        # objective and constraint functions. Instead, we reduce the
        # trust-region radius and check whether the resolution should be
        # reduced and whether the geometry of the interpolation set should be
        # improved. Otherwise, we entertain a classical iteration. The criterion
        # for performing an exceptional jump is taken from NEWUOA.
        if s_norm <= 0.5 * framework.resolution:
            framework.radius *= 0.1
            if radius_save > framework.resolution:
                n_short_steps = 0
                n_very_short_steps = 0
            else:
                n_short_steps += 1
                n_very_short_steps += 1
                if s_norm > 0.1 * framework.resolution:
                    n_very_short_steps = 0
            reduce_resolution = n_short_steps >= 5 or n_very_short_steps >= 3
            if reduce_resolution:
                n_short_steps = 0
                n_very_short_steps = 0
                improve_geometry = False
            else:
                try:
                    k_new, dist_new = framework.get_index_to_remove()
                except np.linalg.LinAlgError:
                    status = ExitStatus.LINALG_ERROR
                    break
                improve_geometry = dist_new > max(framework.radius, 2.0 * framework.resolution)
        else:
            # Increase the penalty parameter if necessary.
            same_best_point = framework.increase_penalty(step)
            if same_best_point:
                # Evaluate the objective and constraint functions.
                try:
                    fun_val, cub_val, ceq_val = _eval(pb, framework, step, options)
                except TargetSuccess:
                    status = ExitStatus.TARGET_SUCCESS
                    success = True
                    break
                except FeasibleSuccess:
                    status = ExitStatus.FEASIBLE_SUCCESS
                    success = True
                    break
                except StopIteration:
                    status = ExitStatus.CALLBACK_SUCCESS
                    success = True
                    break
                except MaxEvalError:
                    status = ExitStatus.MAX_EVAL_WARNING
                    break

                # Perform a second-order correction step if necessary.
                merit_old = framework.merit(framework.x_best, framework.fun_best, framework.cub_best, framework.ceq_best)
                merit_new = framework.merit(framework.x_best + step, fun_val, cub_val, ceq_val)
                if pb.type == 'nonlinearly constrained' and merit_new > merit_old and np.linalg.norm(normal_step) > 0.8 ** 2.0 * framework.radius:
                    soc_step = framework.get_second_order_correction_step(step, options)
                    if np.linalg.norm(soc_step) > 0.0:
                        step += soc_step

                        # Evaluate the objective and constraint functions.
                        try:
                            fun_val, cub_val, ceq_val = _eval(pb, framework, step, options)
                        except TargetSuccess:
                            status = ExitStatus.TARGET_SUCCESS
                            success = True
                            break
                        except FeasibleSuccess:
                            status = ExitStatus.FEASIBLE_SUCCESS
                            success = True
                            break
                        except StopIteration:
                            status = ExitStatus.CALLBACK_SUCCESS
                            success = True
                            break
                        except MaxEvalError:
                            status = ExitStatus.MAX_EVAL_WARNING
                            break

                # Calculate the reduction ratio.
                ratio = framework.get_reduction_ratio(step, fun_val, cub_val, ceq_val)

                # Choose an interpolation point to remove.
                try:
                    k_new = framework.get_index_to_remove(framework.x_best + step)[0]
                except np.linalg.LinAlgError:
                    status = ExitStatus.LINALG_ERROR
                    break

                # Update the interpolation set.
                try:
                    ill_conditioned = framework.models.update_interpolation(k_new, framework.x_best + step, fun_val, cub_val, ceq_val)
                except np.linalg.LinAlgError:
                    status = ExitStatus.LINALG_ERROR
                    break
                framework.set_best_index()

                # Update the trust-region radius.
                framework.update_radius(step, ratio)

                # Attempt to replace the models by the alternative ones.
                if framework.radius <= framework.resolution:
                    if ratio >= 0.01:
                        n_alt_models = 0
                    else:
                        n_alt_models += 1
                        grad = framework.models.fun_grad(framework.x_best)
                        try:
                            grad_alt = framework.models.fun_alt_grad(framework.x_best)
                        except np.linalg.LinAlgError:
                            status = ExitStatus.LINALG_ERROR
                            break
                        if np.linalg.norm(grad) < 10.0 * np.linalg.norm(grad_alt):
                            n_alt_models = 0
                        if n_alt_models >= 3:
                            try:
                                framework.models.reset_models()
                            except np.linalg.LinAlgError:
                                status = ExitStatus.LINALG_ERROR
                                break
                            n_alt_models = 0

                # Update the Lagrange multipliers.
                framework.set_multipliers(framework.x_best + step)

                # Check whether the resolution should be reduced.
                try:
                    k_new, dist_new = framework.get_index_to_remove()
                except np.linalg.LinAlgError:
                    status = ExitStatus.LINALG_ERROR
                    break
                improve_geometry = ill_conditioned or ratio <= 0.1 and dist_new > max(framework.radius, 2.0 * framework.resolution)
                reduce_resolution = radius_save <= framework.resolution and ratio <= 0.1 and not improve_geometry
            else:
                # When increasing the penalty parameter, the best point so far
                # may change. In this case, we restart the iteration.
                reduce_resolution = False
                improve_geometry = False

        # Reduce the resolution if necessary.
        if reduce_resolution:
            if framework.resolution <= options[Options.RHOEND]:
                success = True
                status = ExitStatus.RADIUS_SUCCESS
                break
            framework.reduce_resolution(options)
            framework.decrease_penalty()

            if verbose:
                maxcv_val = pb.maxcv(framework.x_best, framework.cub_best, framework.ceq_best)
                _print_step(f'New trust-region radius: {framework.resolution}', pb, pb.build_x(framework.x_best), framework.fun_best, maxcv_val, pb.n_eval, n_iter)
                print()

        # Improve the geometry of the interpolation set if necessary.
        if improve_geometry:
            try:
                step = framework.get_geometry_step(k_new, options)
            except np.linalg.LinAlgError:
                status = ExitStatus.LINALG_ERROR
                break

            # Evaluate the objective and constraint functions.
            try:
                fun_val, cub_val, ceq_val = _eval(pb, framework, step, options)
            except TargetSuccess:
                status = ExitStatus.TARGET_SUCCESS
                success = True
                break
            except FeasibleSuccess:
                status = ExitStatus.FEASIBLE_SUCCESS
                success = True
                break
            except StopIteration:
                status = ExitStatus.CALLBACK_SUCCESS
                success = True
                break
            except MaxEvalError:
                status = ExitStatus.MAX_EVAL_WARNING
                break

            # Update the interpolation set.
            try:
                framework.models.update_interpolation(k_new, framework.x_best + step, fun_val, cub_val, ceq_val)
            except np.linalg.LinAlgError:
                status = ExitStatus.LINALG_ERROR
                break
            framework.set_best_index()

    return _build_result(pb, framework.penalty, success, status, n_iter, options)


def _get_bounds(bounds, n):
    """
    Uniformize the bounds.
    """
    if bounds is None:
        return Bounds(np.full(n, -np.inf), np.full(n, np.inf))
    elif isinstance(bounds, Bounds):
        if bounds.lb.shape != (n,) or bounds.ub.shape != (n,):
            raise ValueError(f'The bounds must have {n} elements.')
        return bounds
    elif hasattr(bounds, '__len__'):
        bounds = np.asarray(bounds)
        if bounds.shape != (n, 2):
            raise ValueError('The shape of the bounds is not compatible with the number of variables.')
        return Bounds(bounds[:, 0], bounds[:, 1])
    else:
        raise TypeError('The bounds must be an instance of scipy.optimize.Bounds or an array-like object.')


def _get_constraints(constraints):
    """
    Extract the linear and nonlinear constraints.
    """
    if not hasattr(constraints, '__len__'):
        constraints = (constraints,)

    # Extract the linear and nonlinear constraints.
    linear_constraints = []
    nonlinear_constraints = []
    for constraint in constraints:
        if isinstance(constraint, LinearConstraint):
            lb = exact_1d_array(constraint.lb, 'The lower bound of the linear constraints must be a vector.')
            ub = exact_1d_array(constraint.ub, 'The upper bound of the linear constraints must be a vector.')
            linear_constraints.append(LinearConstraint(constraint.A, *np.broadcast_arrays(lb, ub)))
        elif isinstance(constraint, NonlinearConstraint):
            lb = exact_1d_array(constraint.lb, 'The lower bound of the nonlinear constraints must be a vector.')
            ub = exact_1d_array(constraint.ub, 'The upper bound of the nonlinear constraints must be a vector.')
            nonlinear_constraints.append(NonlinearConstraint(constraint.fun, *np.broadcast_arrays(lb, ub)))
        elif isinstance(constraint, dict):
            if 'type' not in constraint or constraint['type'] not in ('eq', 'ineq'):
                raise ValueError('The constraint type must be "eq" or "ineq".')
            if 'fun' not in constraint or not callable(constraint['fun']):
                raise ValueError('The constraint function must be callable.')
            nonlinear_constraints.append({'fun': constraint['fun'], 'type': constraint['type'], 'args': constraint.get('args', ())})
        else:
            raise TypeError('The constraints must be instances of scipy.optimize.LinearConstraint, scipy.optimize.NonlinearConstraint, or dict.')
    return linear_constraints, nonlinear_constraints


def _set_default_options(options, n):
    """
    Set the default options.
    """
    if Options.RHOBEG in options and options[Options.RHOBEG] <= 0.0:
        raise ValueError('The initial trust-region radius must be positive.')
    if Options.RHOEND in options and options[Options.RHOEND] < 0.0:
        raise ValueError('The final trust-region radius must be nonnegative.')
    if Options.RHOBEG in options and Options.RHOEND in options:
        if options[Options.RHOBEG] < options[Options.RHOEND]:
            raise ValueError('The initial trust-region radius must be greater than or equal to the final trust-region radius.')
    elif Options.RHOBEG in options:
        options[Options.RHOEND.value] = np.min([DEFAULT_OPTIONS[Options.RHOEND], options[Options.RHOBEG]])
    elif Options.RHOEND in options:
        options[Options.RHOBEG.value] = np.max([DEFAULT_OPTIONS[Options.RHOBEG], options[Options.RHOEND]])
    else:
        options[Options.RHOBEG.value] = DEFAULT_OPTIONS[Options.RHOBEG]
        options[Options.RHOEND.value] = DEFAULT_OPTIONS[Options.RHOEND]
    options[Options.RHOBEG.value] = float(options[Options.RHOBEG])
    options[Options.RHOEND.value] = float(options[Options.RHOEND])
    if Options.NPT in options and options[Options.NPT] <= 0:
        raise ValueError('The number of interpolation points must be positive.')
    if Options.NPT in options and options[Options.NPT] > ((n + 1) * (n + 2)) // 2:
        raise ValueError(f'The number of interpolation points must be at most {((n + 1) * (n + 2)) // 2}.')
    options.setdefault(Options.NPT.value, DEFAULT_OPTIONS[Options.NPT](n))
    options[Options.NPT.value] = int(options[Options.NPT])
    if Options.MAX_EVAL in options and options[Options.MAX_EVAL] <= 0:
        raise ValueError('The maximum number of function evaluations must be positive.')
    options.setdefault(Options.MAX_EVAL.value, np.max([DEFAULT_OPTIONS[Options.MAX_EVAL](n), options[Options.NPT] + 1]))
    options[Options.MAX_EVAL.value] = int(options[Options.MAX_EVAL])
    if Options.MAX_ITER in options and options[Options.MAX_ITER] <= 0:
        raise ValueError('The maximum number of iterations must be positive.')
    options.setdefault(Options.MAX_ITER.value, DEFAULT_OPTIONS[Options.MAX_ITER](n))
    options[Options.MAX_ITER.value] = int(options[Options.MAX_ITER])
    options.setdefault(Options.TARGET.value, DEFAULT_OPTIONS[Options.TARGET])
    options[Options.TARGET.value] = float(options[Options.TARGET])
    options.setdefault(Options.FEASIBILITY_TOL.value, DEFAULT_OPTIONS[Options.FEASIBILITY_TOL])
    options[Options.FEASIBILITY_TOL.value] = float(options[Options.FEASIBILITY_TOL])
    options.setdefault(Options.VERBOSE.value, DEFAULT_OPTIONS[Options.VERBOSE])
    options[Options.VERBOSE.value] = bool(options[Options.VERBOSE])
    options.setdefault(Options.SCALE.value, DEFAULT_OPTIONS[Options.SCALE])
    options[Options.SCALE.value] = bool(options[Options.SCALE])
    options.setdefault(Options.FILTER_SIZE.value, DEFAULT_OPTIONS[Options.FILTER_SIZE])
    options[Options.FILTER_SIZE.value] = int(options[Options.FILTER_SIZE])
    options.setdefault(Options.STORE_HISTORY.value, DEFAULT_OPTIONS[Options.STORE_HISTORY])
    options[Options.STORE_HISTORY.value] = bool(options[Options.STORE_HISTORY])
    options.setdefault(Options.HISTORY_SIZE.value, DEFAULT_OPTIONS[Options.HISTORY_SIZE])
    options[Options.HISTORY_SIZE.value] = int(options[Options.HISTORY_SIZE])
    options.setdefault(Options.DEBUG.value, DEFAULT_OPTIONS[Options.DEBUG])
    options[Options.DEBUG.value] = bool(options[Options.DEBUG])

    # Check whether they are any unknown options.
    for key in options:
        if key not in Options.__members__.values():
            warnings.warn(f'Unknown option: {key}.', RuntimeWarning, 3)


def _eval(pb, framework, step, options):
    """
    Evaluate the objective and constraint functions.
    """
    if pb.n_eval >= options[Options.MAX_EVAL]:
        raise MaxEvalError
    x_eval = framework.x_best + step
    fun_val, cub_val, ceq_val = pb(x_eval)
    r_val = pb.maxcv(x_eval, cub_val, ceq_val)
    if fun_val <= options[Options.TARGET] and r_val <= options[Options.FEASIBILITY_TOL]:
        raise TargetSuccess
    if pb.is_feasibility and r_val <= options[Options.FEASIBILITY_TOL]:
        raise FeasibleSuccess
    return fun_val, cub_val, ceq_val


def _build_result(pb, penalty, success, status, n_iter, options):
    """
    Build the result of the optimization process.
    """
    # Build the result.
    x, fun, maxcv = pb.best_eval(penalty)
    if status not in [ExitStatus.TARGET_SUCCESS, ExitStatus.FEASIBLE_SUCCESS]:
        success = success and maxcv <= options[Options.FEASIBILITY_TOL]
    result = OptimizeResult()
    result.message = {
        ExitStatus.RADIUS_SUCCESS: 'The lower bound for the trust-region radius has been reached',
        ExitStatus.TARGET_SUCCESS: 'The target objective function value has been reached',
        ExitStatus.FIXED_SUCCESS: 'All variables are fixed by the bound constraints',
        ExitStatus.CALLBACK_SUCCESS: 'The callback requested to stop the optimization procedure',
        ExitStatus.FEASIBLE_SUCCESS: 'The feasibility problem received has been solved successfully',
        ExitStatus.MAX_EVAL_WARNING: 'The maximum number of function evaluations has been exceeded',
        ExitStatus.MAX_ITER_WARNING: 'The maximum number of iterations has been exceeded',
        ExitStatus.INFEASIBLE_ERROR: 'The bound constraints are infeasible',
        ExitStatus.LINALG_ERROR: 'A linear algebra error occurred',
    }.get(status, 'Unknown exit status')
    result.success = success
    result.status = status.value
    result.x = pb.build_x(x)
    result.fun = fun
    result.maxcv = maxcv
    result.nfev = pb.n_eval
    result.nit = n_iter
    if options[Options.STORE_HISTORY]:
        result.fun_history = pb.fun_history
        result.maxcv_history = pb.maxcv_history

    # Print the result if requested.
    if options[Options.VERBOSE]:
        _print_step(result.message, pb, result.x, result.fun, result.maxcv, result.nfev, result.nit)
    return result


def _print_step(message, pb, x, fun_val, r_val, n_eval, n_iter):
    """
    Print information about the current state of the optimization process.
    """
    print()
    print(f'{message}.')
    print(f'Number of function evaluations: {n_eval}.')
    print(f'Number of iterations: {n_iter}.')
    if not pb.is_feasibility:
        print(f'Least value of {pb.fun_name}: {fun_val}.')
    print(f'Maximum constraint violation: {r_val}.')
    with np.printoptions(**PRINT_OPTIONS):
        print(f'Corresponding point: {x}.')
