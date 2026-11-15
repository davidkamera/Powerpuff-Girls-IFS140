import statistics
from scipy import stats
import matplotlib.pyplot as plt

#Nitrate Measurements for each group
control = [10, 12, 11, 13, 9]
treatment_b = [15, 16, 14, 17, 13]

#Calculate mean for each group
control_mean = statistics.mean(control)
treatment_b_mean = statistics.mean(treatment_b)

#Calculate the 95% confidence intervals
control_ci = stats.t.interval(0.95, df=len(control)-1, loc=control_mean, scale=stats.sem(control))

treatment_b_ci = stats.t.interval(0.95, df=len(treatment_b) - 1, loc= treatment_b_mean, scale= stats.sem(treatment_b))

#Display results
print("Control mean:", round(control_mean, 2))
print("Control 95% CI:", control_ci)

print("Treatment B mean:", round(treatment_b_mean, 2))
print("Treatment B 95% CI:", treatment_b_ci)

#Prepare chart
means = (control_mean, treatment_b_mean)
labels = ("Control", "Treatment B")

lower_errors = (control_mean - control_ci[0], treatment_b_mean - treatment_b_ci[0])

upper_errors = (control_ci[1] - control_mean, treatment_b_ci[1] - treatment_b_mean)

#Plot means with 95% confidence intervals
plt.errorbar(labels, means, yerr=[lower_errors, upper_errors], capsize=6)

plt.title("Nitrate Measurements with 95% Confidence Intervals")
plt.xlabel("Treatment Groups")
plt.ylabel("Mean Nitrate Level")
plt.tight_layout()
plt.show()