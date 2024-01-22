def compare_stack_traces(a_parts, b_parts):
    """

    :param a_parts:
    :param b_parts:
    :return: top_trace_matching_parts, bottom_trace_matching_parts
    """

    def compare_stack_traces_tops():
        collector = []
        for a_part, b_part in zip(a_parts, b_parts):
            if a_part == b_part:
                collector.append(a_part)
            else:
                break
        return collector

    def lcs(s1, s2):
        matrix = [[[] for x in range(len(s2))] for x in range(len(s1))]
        for i in range(len(s1)):
            for j in range(len(s2)):
                if s1[i] == s2[j]:
                    if i == 0 or j == 0:
                        matrix[i][j] = list(s1[i])
                    else:
                        matrix[i][j] = matrix[i - 1][j - 1] + list(s1[i])
                else:
                    matrix[i][j] = max(matrix[i - 1][j], matrix[i][j - 1], key=len)

        cs = matrix[-1][-1]

        return len(cs), cs

    lcs_out = lcs(a_parts, b_parts)
    print(lcs_out)
    top_parts_in_common = compare_stack_traces_tops()
    a_parts.reverse()
    b_parts.reverse()
    bottom_parts_in_common = compare_stack_traces_tops()
    return tuple([top_parts_in_common, bottom_parts_in_common, lcs_out])


def main():
    # first = "org.activiti.spring.test.jobexecutor.SpringAsyncExecutorTest.testHappyJobExecutorPath(SpringAsyncExecutorTest.java:45) org.activiti.engine.impl.db.DbSqlSession.flushUpdates(DbSqlSession.java:851) org.activiti.engine.impl.db.DbSqlSession.flush(DbSqlSession.java:524) org.activiti.engine.impl.interceptor.CommandContext.flushSessions(CommandContext.java:237) org.activiti.engine.impl.interceptor.CommandContext.close(CommandContext.java:102) org.activiti.engine.impl.interceptor.CommandContextInterceptor.execute(CommandContextInterceptor.java:72) org.activiti.spring.SpringTransactionInterceptor$1.doInTransaction(SpringTransactionInterceptor.java:47) org.activiti.spring.SpringTransactionInterceptor.execute(SpringTransactionInterceptor.java:45) org.activiti.engine.impl.interceptor.LogInterceptor.execute(LogInterceptor.java:29) org.activiti.engine.impl.cfg.CommandExecutorImpl.execute(CommandExecutorImpl.java:44) org.activiti.engine.impl.cfg.CommandExecutorImpl.execute(CommandExecutorImpl.java:39) org.activiti.engine.impl.RepositoryServiceImpl.deleteDeployment(RepositoryServiceImpl.java:95) org.activiti.spring.impl.test.CleanTestExecutionListener.afterTestClass(CleanTestExecutionListener.java:24)".split(
    #     ' ')
    # second = "org.activiti.spring.test.jobexecutor.SpringAsyncExecutorTest.testHappyJobExecutorPath(SpringAsyncExecutorTest.java:45) org.activiti.engine.impl.db.DbSqlSession.flushDeleteEntities(DbSqlSession.java:914) org.activiti.engine.impl.db.DbSqlSession.flushDeletes(DbSqlSession.java:871) org.activiti.engine.impl.db.DbSqlSession.flush(DbSqlSession.java:525) org.activiti.engine.impl.interceptor.CommandContext.flushSessions(CommandContext.java:237) org.activiti.engine.impl.interceptor.CommandContext.close(CommandContext.java:102) org.activiti.engine.impl.interceptor.CommandContextInterceptor.execute(CommandContextInterceptor.java:72) org.activiti.spring.SpringTransactionInterceptor$1.doInTransaction(SpringTransactionInterceptor.java:47) org.activiti.spring.SpringTransactionInterceptor.execute(SpringTransactionInterceptor.java:45) org.activiti.engine.impl.interceptor.LogInterceptor.execute(LogInterceptor.java:29) org.activiti.engine.impl.cfg.CommandExecutorImpl.execute(CommandExecutorImpl.java:44) org.activiti.engine.impl.cfg.CommandExecutorImpl.execute(CommandExecutorImpl.java:39) org.activiti.engine.impl.RepositoryServiceImpl.deleteDeployment(RepositoryServiceImpl.java:95) org.activiti.spring.impl.test.CleanTestExecutionListener.afterTestClass(CleanTestExecutionListener.java:24)".split(
    # ' ')
    first = ['NoFail']
    second = ['NoFail']
    out = compare_stack_traces(first, second)
    # print(out)
    # print(len(first))
    # print(len(second))
    # print(len(out[0]))
    # print(len(out[1]))
    # print(len(out[2]))


if __name__ == "__main__":
    main()
