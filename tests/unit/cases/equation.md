Finally, like performance, reliability can be measured.  We can improve availability either taking longer between failures (MTTF) or by making the app reboot faster---___mean time between repairs___ (___MTTR___)---as this equation shows: 
<center>
$$
\mbox{unavailability} \approx \frac{\mbox{MTTR}}{\mbox{MTTF}}
$$
</center>
 While it is hard to measure improvements in MTTF, as it can take a long time to record failures, we can easily measure MTTR. We just crash a computer and see how long it takes the app to reboot. And what we can measure, we can improve. Hence, it may be much more cost-effective to try to improve MTTR than to improve MTTF since it is easier to measure progress. However, they are not mutually exclusive, so developers can try to increase dependability by following both paths.