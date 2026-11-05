# 统一 benchmark 样例集

- 生成时间：2026-11-05T18:34:32
- 来源：11 个；每个来源 12 条，seed=42
- 总计：132 条

## 来源

| 来源 | 可用 | 版本 | 原始条数 | 抽样 | 许可 |
|:---|:---:|:---|:---:|:---:|:---|
| tau2-bench | ✅ | cc1df47 | 114 | 12 | MIT |
| bfcl-v4 | ✅ | 6ea5797 | 640 | 12 | Apache-2.0 |
| rgb | ✅ | 65ec39e | 300 | 12 | CC BY-NC-SA 4.0 |
| multihop-rag | ✅ | c1c1287 | 2556 | 12 | ODC-BY 1.0 |
| cfbench | ✅ | 0bcbf9b | 1000 | 12 | 未附 LICENSE（上游仓库） |
| gaia | ✅ | unknown | 165 | 12 | see HuggingFace dataset card |
| humaneval | ✅ | b9453e8 | 164 | 12 | MIT |
| mbpp | ✅ | unknown | 974 | 12 | Apache-2.0 |
| swe-bench | ✅ | unknown | 500 | 12 | MIT (see repo) |
| webarena | ✅ | unknown | 812 | 12 | Apache-2.0 |
| osworld | ✅ | unknown | 418 | 12 | Apache-2.0 |

## 分类

- coding: 12
- customer_service: 12
- easy_answerable: 4
- easy_unanswerable: 3
- function_completion: 12
- function_generation: 12
- general_assistant: 12
- hard_answerable: 2
- hard_unanswerable: 2
- hard_unknown: 1
- os_chrome: 1
- os_excel: 1
- os_gimp: 1
- os_libreoffice_calc: 1
- os_libreoffice_impress: 1
- os_libreoffice_writer: 1
- os_multi_app: 1
- os_multi_apps: 1
- os_os: 1
- os_ppt: 1
- os_thunderbird: 1
- os_vlc: 1
- rag_multihop_comparison_query: 3
- rag_multihop_inference_query: 3
- rag_multihop_null_query: 3
- rag_multihop_temporal_query: 3
- rag_rgb: 12
- tool_calling_irrelevance: 6
- tool_calling_simple: 6
- web: 12

## AgentGuide Bucket

- adversarial: 14
- capability: 106
- multi_turn: 12

## 评测范围（模型能力 / 场景工具）

- model_capability: 60
- scenario_tool: 72

## 执行方式

- external: 60
- native: 48
- sandbox_required: 24

## 样例

| ID | 来源 | Bucket | 范围 | 类别 | 任务 | 评分 |
|:---|:---|:---|:---|:---|:---|:---|
| bfcl-irrelevance_45 | bfcl-v4 | adversarial | scenario_tool | tool_calling_irrelevance | Calculate the sine of 45 degree. | code |
| bfcl-irrelevance_113 | bfcl-v4 | adversarial | scenario_tool | tool_calling_irrelevance | Find me restaurants in London | code |
| bfcl-irrelevance_9 | bfcl-v4 | adversarial | scenario_tool | tool_calling_irrelevance | Find the definite integral of f(x)=x^2 from x=1 to x=3. | code |
| bfcl-irrelevance_85 | bfcl-v4 | adversarial | scenario_tool | tool_calling_irrelevance | Who won the presidential election in 2020? | code |
| bfcl-irrelevance_105 | bfcl-v4 | adversarial | scenario_tool | tool_calling_irrelevance | What are the top five flower species for pollination in Sout | code |
| bfcl-irrelevance_197 | bfcl-v4 | adversarial | scenario_tool | tool_calling_irrelevance | Who won the game of Monopoly last night? | code |
| bfcl-simple_python_221 | bfcl-v4 | capability | scenario_tool | tool_calling_simple | What will be the population growth in London over the next f | code |
| bfcl-simple_python_182 | bfcl-v4 | capability | scenario_tool | tool_calling_simple | Retrieve all the lawsuit details for case number XYZ123. | code |
| bfcl-simple_python_112 | bfcl-v4 | capability | scenario_tool | tool_calling_simple | Calculate the probability of drawing a king from a deck of c | code |
| bfcl-simple_python_157 | bfcl-v4 | capability | scenario_tool | tool_calling_simple | Find out if an individual John Doe with a birthday 01-01-198 | code |
| bfcl-simple_python_99 | bfcl-v4 | capability | scenario_tool | tool_calling_simple | Plot a sine wave from 0 to 2 pi with a frequency of 5 Hz. | code |
| bfcl-simple_python_12 | bfcl-v4 | capability | scenario_tool | tool_calling_simple | Calculate the circumference of a circle with radius 3 | code |
| cfbench-227 | cfbench | capability | model_capability | easy_answerable | 请根据我提供的正确答案对下列来自于智工回答进行评分，评分标准为5：回答正确、全面4：回答正确、但不全面3：回答错误、没有 | mixed |
| cfbench-682 | cfbench | capability | model_capability | easy_answerable | 在本任务中，你需要面对一个陈述和一个解释，以此来评判陈述的准确性。若该解释支持或未能否定该陈述，则应将该实例标记为“真” | mixed |
| cfbench-852 | cfbench | capability | model_capability | easy_answerable | Premise: "A man in a blue vest is sitting on a ledge and a c | mixed |
| cfbench-273 | cfbench | capability | model_capability | easy_answerable | 以下是关于法理学的单项选择题，共6道题目，请直接给出正确答案的选项。 输出的答案共有6行。输出答案的格式为字母+选项。题 | mixed |
| cfbench-346 | cfbench | adversarial | model_capability | easy_unanswerable | "请对我提供的“段落”进行改写或润色，具体要求如下： 1、如果段落中存在拼音、错别字、语句不通顺，请纠正后再进行润色；  | mixed |
| cfbench-455 | cfbench | adversarial | model_capability | easy_unanswerable | 鉴赏：“白日依山尽，黄河入海流；欲穷千里目，更上一层楼”。结果需要体现诗歌背景、作者的表达思想；简洁明了，不超过600字 | mixed |
| cfbench-344 | cfbench | adversarial | model_capability | easy_unanswerable | "# 角色：口语转换为书面化用语机器 ## 背景：我会给你一段调解员和当事人的司法调解口语对话内容，你需要将口语转为书面 | mixed |
| cfbench-270 | cfbench | capability | model_capability | hard_answerable | "下面是一段理想汽车的电销客服与潜在购车客户的聊天记录，'''1:好。|0:喂喂，你好。|1:你好。|0:嗯，你哪位？| | mixed |
| cfbench-21 | cfbench | capability | model_capability | hard_answerable | 你是一个内容理解助手, 我给你多组内容，你帮我识别、归纳出产品词（如手机、积木等，只归纳产品类型词，不需要具体型号和特征 | mixed |
| cfbench-467 | cfbench | adversarial | model_capability | hard_unanswerable | 曼卡拉奇， 又叫播种棋、 池塘棋、 营盘棋。 它是一种容器式的棋盘游戏， 是一种非常古老的民间棋类游戏。 它的流行特别广 | mixed |
| cfbench-375 | cfbench | adversarial | model_capability | hard_unanswerable | 在一个炎热的夏日，作为一名中医医生，你决定在微博上发起一个活动，科普“天气热没胃口”的现象。请用一篇博文的形式，代入古代 | mixed |
| cfbench-810 | cfbench | capability | model_capability | hard_unknown |  | mixed |
| gaia-42576abe-0deb-4869-8c63-225c2d75a95a | gaia | capability | scenario_tool | general_assistant | In the fictional language of Tizin, basic sentences are arra | mixed |
| gaia-a26649c6-1cb2-470a-871e-6910c64c3e53 | gaia | capability | scenario_tool | general_assistant | What is the absolute difference in tens of thousands between | mixed |
| gaia-e1fc63a2-da7a-432f-be78-7c4a95598703 | gaia | capability | scenario_tool | general_assistant | If Eliud Kipchoge could maintain his record-making marathon  | mixed |
| gaia-708b99c5-e4a7-49cb-a5cf-933c8d46470d | gaia | capability | scenario_tool | general_assistant | On the DeepFruits fruit detection graph on Connected Papers  | mixed |
| gaia-4d0aa727-86b1-406b-9b33-f870dd14a4a5 | gaia | capability | scenario_tool | general_assistant | The attached file lists the locomotives owned by a local rai | mixed |
| gaia-935e2cff-ae78-4218-b3f5-115589b19dae | gaia | capability | scenario_tool | general_assistant | In the year 2022, and before December, what does "R" stand f | mixed |
| gaia-ebbc1f13-d24d-40df-9068-adcf735b4240 | gaia | capability | scenario_tool | general_assistant | The Latin root of the Yola word "gimlie" shares a spelling w | mixed |
| gaia-8e867cd7-cff9-4e6c-867a-ff5ddc2550be | gaia | capability | scenario_tool | general_assistant | How many studio albums were published by Mercedes Sosa betwe | mixed |
| gaia-4d51c4bf-4b0e-4f3d-897b-3f6687a7d9f2 | gaia | capability | scenario_tool | general_assistant | This spreadsheet contains a list of clients for a retractabl | mixed |
| gaia-5a0c1adf-205e-4841-a666-7c3ef95def9d | gaia | capability | scenario_tool | general_assistant | What is the first name of the only Malko Competition recipie | mixed |
| gaia-2a649bb1-795f-4a01-b3be-9a01868dae73 | gaia | capability | scenario_tool | general_assistant | What are the EC numbers of the two most commonly used chemic | mixed |
| gaia-67e8878b-5cef-4375-804e-e6291fdbe78a | gaia | capability | scenario_tool | general_assistant | The attached PDF lists accommodations in the resort communit | mixed |
| humaneval-HumanEval-159 | humaneval | capability | model_capability | function_completion |  def eat(number, need, remaining):     """     You're a hung | unit_test |
| humaneval-HumanEval-160 | humaneval | capability | model_capability | function_completion |  def do_algebra(operator, operand):     """     Given two li | unit_test |
| humaneval-HumanEval-101 | humaneval | capability | model_capability | function_completion |  def words_string(s):     """     You will be given a string | unit_test |
| humaneval-HumanEval-80 | humaneval | capability | model_capability | function_completion |  def is_happy(s):     """You are given a string s.     Your  | unit_test |
| humaneval-HumanEval-100 | humaneval | capability | model_capability | function_completion |  def make_a_pile(n):     """     Given a positive integer n, | unit_test |
| humaneval-HumanEval-24 | humaneval | capability | model_capability | function_completion |   def largest_divisor(n: int) -> int:     """ For a given nu | unit_test |
| humaneval-HumanEval-8 | humaneval | capability | model_capability | function_completion | from typing import List, Tuple   def sum_product(numbers: Li | unit_test |
| humaneval-HumanEval-62 | humaneval | capability | model_capability | function_completion |   def derivative(xs: list):     """ xs represent coefficient | unit_test |
| humaneval-HumanEval-22 | humaneval | capability | model_capability | function_completion | from typing import List, Any   def filter_integers(values: L | unit_test |
| humaneval-HumanEval-14 | humaneval | capability | model_capability | function_completion | from typing import List   def all_prefixes(string: str) -> L | unit_test |
| humaneval-HumanEval-78 | humaneval | capability | model_capability | function_completion |  def hex_key(num):     """You have been tasked to write a fu | unit_test |
| humaneval-HumanEval-52 | humaneval | capability | model_capability | function_completion |   def below_threshold(l: list, t: int):     """Return True i | unit_test |
| mbpp-771 | mbpp | capability | model_capability | function_generation | Write a function to check if the given expression is balance | unit_test |
| mbpp-785 | mbpp | capability | model_capability | function_generation | Write a function to convert tuple string to integer tuple. | unit_test |
| mbpp-974 | mbpp | capability | model_capability | function_generation | Write a function to find the minimum total path sum in the g | unit_test |
| mbpp-911 | mbpp | capability | model_capability | function_generation | Write a function to compute maximum product of three numbers | unit_test |
| mbpp-70 | mbpp | capability | model_capability | function_generation | Write a function to find whether all the given tuples have e | unit_test |
| mbpp-542 | mbpp | capability | model_capability | function_generation | Write a function to replace all occurrences of spaces, comma | unit_test |
| mbpp-181 | mbpp | capability | model_capability | function_generation | Write a function to find the longest common prefix in the gi | unit_test |
| mbpp-642 | mbpp | capability | model_capability | function_generation | Write a function to remove similar rows from the given tuple | unit_test |
| mbpp-875 | mbpp | capability | model_capability | function_generation | Write a function to find the minimum difference in the tuple | unit_test |
| mbpp-23 | mbpp | capability | model_capability | function_generation | Write a python function to find the maximum sum of elements  | unit_test |
| mbpp-211 | mbpp | capability | model_capability | function_generation | Write a python function to count numbers whose oth and nth b | unit_test |
| mbpp-545 | mbpp | capability | model_capability | function_generation | Write a python function to toggle only first and last bits o | unit_test |
| multihop-1857 | multihop-rag | capability | model_capability | rag_multihop_comparison_query | Does the Polygon article on 'Spider-Man: Across the Spider-V | mixed |
| multihop-317 | multihop-rag | capability | model_capability | rag_multihop_comparison_query | Does the 'Essentially Sports' article suggest that the NBA's | mixed |
| multihop-2468 | multihop-rag | capability | model_capability | rag_multihop_comparison_query | Does the Sporting News article anticipate an impressive perf | mixed |
| multihop-2135 | multihop-rag | capability | model_capability | rag_multihop_inference_query | Who is the individual associated with the rise of artificial | mixed |
| multihop-616 | multihop-rag | capability | model_capability | rag_multihop_inference_query | Who is the individual associated with the cryptocurrency ind | mixed |
| multihop-1191 | multihop-rag | capability | model_capability | rag_multihop_inference_query | Who is the individual that, according to different reports f | mixed |
| multihop-281 | multihop-rag | adversarial | model_capability | rag_multihop_null_query | Considering the information from an article by The Times of  | mixed |
| multihop-1067 | multihop-rag | adversarial | model_capability | rag_multihop_null_query | Considering the information from an article in The Wall Stre | mixed |
| multihop-49 | multihop-rag | adversarial | model_capability | rag_multihop_null_query | Considering an article from The Times of India detailing Suh | mixed |
| multihop-1673 | multihop-rag | capability | model_capability | rag_multihop_temporal_query | Did TechCrunch report on October 31, 2023, that Google paid  | mixed |
| multihop-372 | multihop-rag | capability | model_capability | rag_multihop_temporal_query | Between the TalkSport report on the Manchester United takeov | mixed |
| multihop-2363 | multihop-rag | capability | model_capability | rag_multihop_temporal_query | Between the TechCrunch report on Sam Bankman-Fried's crimina | mixed |
| osworld-35253b65-1c19-4304-8aa4-6884b8218fc0 | osworld | capability | scenario_tool | os_chrome | Hey, I need a quick way back to this site. Could you whip up | code |
| osworld-abed40dc-063f-4598-8ba5-9fe749c0615d | osworld | capability | scenario_tool | os_excel | Check the names in column "Names with duplicates" and put th | code |
| osworld-e19bd559-633b-4b02-940f-d946248f088e | osworld | capability | scenario_tool | os_gimp | Could you tone down the brightness of my photo at desktop? | code |
| osworld-abed40dc-063f-4598-8ba5-9fe749c0615d | osworld | capability | scenario_tool | os_libreoffice_calc | Check the names in column "Names with duplicates" and put th | code |
| osworld-af2d657a-e6b3-4c6a-9f67-9e3ed015974c | osworld | capability | scenario_tool | os_libreoffice_impress | In the first slide, insert the title "Happy Family" and make | code |
| osworld-0e763496-b6bb-4508-a427-fad0b6c3e195 | osworld | capability | scenario_tool | os_libreoffice_writer | Change the font to "Times New Roman" throughout the text. | code |
| osworld-6d72aad6-187a-4392-a4c4-ed87269c51cf | osworld | capability | scenario_tool | os_multi_app | Could you please converting MS Office PowerPoint presentatio | code |
| osworld-74d5859f-ed66-4d3e-aa0e-93d7a592ce41 | osworld | capability | scenario_tool | os_multi_apps | Help me to set up an initial web extension project with help | code |
| osworld-ec4e3f68-9ea4-4c18-a5c9-69f89d1178b3 | osworld | capability | scenario_tool | os_os | Can you remove vim from favorite app in 'favorites'? | code |
| osworld-3b27600c-3668-4abd-8f84-7bcdebbccbdb | osworld | capability | scenario_tool | os_ppt | Please make the background blue on all my slides. I was stuc | code |
| osworld-3f28fe4f-5d9d-4994-a456-efd78cfae1a3 | osworld | capability | scenario_tool | os_thunderbird | Set up a plain text signature for my email account in Thunde | code |
| osworld-215dfd39-f493-4bc3-a027-8a97d72c61bf | osworld | capability | scenario_tool | os_vlc | Can you disable the cone icon in the splash screen? I am tir | code |
| rgb-zh-167 | rgb | capability | model_capability | rag_rgb | 2022年金鹰奖最佳电视剧 | mixed |
| rgb-zh-71 | rgb | capability | model_capability | rag_rgb | 神舟十三号飞船的成员有哪些 | mixed |
| rgb-zh-94 | rgb | capability | model_capability | rag_rgb | 2022年芦山地震是的震级 | mixed |
| rgb-zh-198 | rgb | capability | model_capability | rag_rgb | 首架C919的交付日时间？ | mixed |
| rgb-zh-161 | rgb | capability | model_capability | rag_rgb | 《三体》动画是谁制作的？ | mixed |
| rgb-zh-149 | rgb | capability | model_capability | rag_rgb | 中国女篮在2022世界杯小组赛中最终排名？ | mixed |
| rgb-zh-147 | rgb | capability | model_capability | rag_rgb | 唐山烧烤店打人案件主犯被判多少年？ | mixed |
| rgb-zh-91 | rgb | capability | model_capability | rag_rgb | 美团2022年第一季度营收是多少？ | mixed |
| rgb-zh-210 | rgb | capability | model_capability | rag_rgb | 2023年IRONMAN世界锦标赛男子赛事在哪举行 | mixed |
| rgb-zh-109 | rgb | capability | model_capability | rag_rgb | 《胡同儿》的导演是谁 | mixed |
| rgb-zh-164 | rgb | capability | model_capability | rag_rgb | 2022年女篮世界杯中国女篮成绩 | mixed |
| rgb-zh-171 | rgb | capability | model_capability | rag_rgb | 乌镇峰会举办时间 | mixed |
| swebench-django__django-16901 | swe-bench | capability | scenario_tool | coding | On databases lacking XOR, Q(…) ^ Q(…) ^ Q(…) wrongly interpr | code |
| swebench-sympy__sympy-19783 | swe-bench | capability | scenario_tool | coding | Dagger() * IdentityOperator() is not simplified As discussed | code |
| swebench-sympy__sympy-18763 | swe-bench | capability | scenario_tool | coding | Incorrect parenthesizing of Subs Here is an example. ```pyt | code |
| swebench-astropy__astropy-14309 | swe-bench | capability | scenario_tool | coding | IndexError: tuple index out of range in identify_format (io. | code |
| swebench-sympy__sympy-13878 | swe-bench | capability | scenario_tool | coding | Precompute the CDF of several distributions where integratio | code |
| swebench-matplotlib__matplotlib-26466 | swe-bench | capability | scenario_tool | coding | Updating an array passed as the xy parameter to annotate upd | code |
| swebench-django__django-13195 | swe-bench | capability | scenario_tool | coding | HttpResponse.delete_cookie() should preserve cookie's samesi | code |
| swebench-scikit-learn__scikit-learn-15100 | swe-bench | capability | scenario_tool | coding | strip_accents_unicode fails to strip accents from strings th | code |
| swebench-django__django-14170 | swe-bench | capability | scenario_tool | coding | Query optimization in YearLookup breaks filtering by "__iso_ | code |
| swebench-sympy__sympy-23824 | swe-bench | capability | scenario_tool | coding | physics.hep.kahane_simplify() incorrectly reverses order of  | code |
| swebench-django__django-11239 | swe-bench | capability | scenario_tool | coding | Add support for postgresql client certificates and key to db | code |
| swebench-matplotlib__matplotlib-13989 | swe-bench | capability | scenario_tool | coding | hist() no longer respects range=... when density=True <!--To | code |
| tau2-retail-29 | tau2-bench | multi_turn | scenario_tool | customer_service | You want to exchange your skateboard for a shorter bamboo ma | mixed |
| tau2-retail-88 | tau2-bench | multi_turn | scenario_tool | customer_service | You want to change the book shelf to 4 foot but with the sam | mixed |
| tau2-retail-76 | tau2-bench | multi_turn | scenario_tool | customer_service | You ordered a fleece jacket by mistake and want to remove it | mixed |
| tau2-retail-42 | tau2-bench | multi_turn | scenario_tool | customer_service | You just created your user id mei_patel_7272 and ordered som | mixed |
| tau2-retail-70 | tau2-bench | multi_turn | scenario_tool | customer_service | You recently received a helmet but you are not happy with it | mixed |
| tau2-retail-84 | tau2-bench | multi_turn | scenario_tool | customer_service | You received two tablets and you only need one. You want to  | mixed |
| tau2-retail-102 | tau2-bench | multi_turn | scenario_tool | customer_service | You just placed an order with two watches, you want to chang | mixed |
| tau2-retail-19 | tau2-bench | multi_turn | scenario_tool | customer_service | You want to return the water bottle, and exchange the pet be | mixed |
| tau2-retail-109 | tau2-bench | multi_turn | scenario_tool | customer_service | You live on Elm Avenue in Houston, and recently you moved to | mixed |
| tau2-retail-30 | tau2-bench | multi_turn | scenario_tool | customer_service | You just received your tablet and it was damaged when you op | mixed |
| tau2-retail-15 | tau2-bench | multi_turn | scenario_tool | customer_service | You want to modify the pending boots to a size 8, and want t | mixed |
| tau2-retail-12 | tau2-bench | multi_turn | scenario_tool | customer_service | You just got into gaming and want to cancel or return everyt | mixed |
| webarena-569 | webarena | capability | scenario_tool | web | Invite Benoît and Abishek as collaborator to my HTML5 markup | code |
| webarena-481 | webarena | capability | scenario_tool | web | Abishek wants to check my dotfile configurations. Please inv | code |
| webarena-215 | webarena | capability | scenario_tool | web | What are the key aspects that the customers don't like about | code |
| webarena-763 | webarena | capability | scenario_tool | web | Find the walkway to the closest Trader Joe's from 401 Shady  | code |
| webarena-764 | webarena | capability | scenario_tool | web | Find the walkway to the closest Target from 401 Shady Ave, P | code |
| webarena-717 | webarena | capability | scenario_tool | web | Thumbs down the top 4 post ever in movies. | code |
| webarena-462 | webarena | capability | scenario_tool | web | Increase the price of this product by 10% | code |
| webarena-460 | webarena | capability | scenario_tool | web | Reduce the price of this product by 15% | code |
| webarena-710 | webarena | capability | scenario_tool | web | Create a shipping report from 08/05/2022 to 03/01/2023 | code |
| webarena-577 | webarena | capability | scenario_tool | web | Add the following users to my GitHub timeline item managemen | code |
| webarena-286 | webarena | capability | scenario_tool | web | Show the least expensive ssd hard drive with a minimum stora | code |
| webarena-4 | webarena | capability | scenario_tool | web | What are the top-3 best-selling product in Jan 2023 | code |
